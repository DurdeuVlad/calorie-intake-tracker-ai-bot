import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db.base import session_scope
from app.db.models.messaging import MessagingOutboundMessage, TelegramAccessGrant
from app.db.models.users import FoodUser
from app.messaging import inbox_worker, ingress
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging.inbound_message import InboundMessage
from app.messaging.inbox_worker import InboxWorkerDeps


class RecordingJournal:
    default_timezone = "Europe/Bucharest"

    def __init__(self):
        self.calls: list[int] = []

    async def handle(self, session, user, conversation_id, text):
        self.calls.append(user.telegram_user_id)
        return "journal accepted"


@pytest.fixture(autouse=True)
def _bootstrap_admin(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(type(settings), "admin_telegram_user_id_set", property(lambda self: {"101"}))
    monkeypatch.setattr(type(settings), "allowed_telegram_user_id_set", property(lambda self: set()))


def message(event_id: str, sender: int, chat: int, text: str) -> InboundMessage:
    return InboundMessage(
        provider="telegram", event_id=event_id, user_id=str(sender), conversation_id=str(chat),
        display_name=f"User {sender}", language_code="en", text=text, caption=None,
    )


@pytest.mark.asyncio
async def test_admin_grants_are_private_persistent_and_journals_stay_separate():
    journal = RecordingJournal()
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([]))

    async with session_scope() as session:
        await ingress.accept(session, message("admin-add", 101, 101, "/adduser 202"))
    assert await inbox_worker.process_one(deps)

    async with session_scope() as session:
        grants = (await session.execute(select(TelegramAccessGrant))).scalars().all()
        assert {(g.telegram_user_id, g.is_admin, g.active) for g in grants} == {(101, True, True), (202, False, True)}

    async with session_scope() as session:
        await ingress.accept(session, message("user-journal", 202, 202, "lunch"))
        await ingress.accept(session, message("admin-journal", 101, 101, "breakfast"))
    assert await inbox_worker.process_one(deps)
    assert await inbox_worker.process_one(deps)
    assert journal.calls == [202, 101]

    async with session_scope() as session:
        users = (await session.execute(select(FoodUser).order_by(FoodUser.telegram_user_id))).scalars().all()
        assert [u.telegram_user_id for u in users] == [101, 202]
        assert users[0].id != users[1].id

    # A group command does not disclose the target ID and cannot change access.
    async with session_scope() as session:
        await ingress.accept(session, message("group-remove", 101, -1001, "/removeuser 202"))
    assert await inbox_worker.process_one(deps)
    async with session_scope() as session:
        group_reply = (await session.execute(
            select(MessagingOutboundMessage).where(MessagingOutboundMessage.conversation_id == "-1001")
        )).scalar_one()
        assert "private chat" in group_reply.text
        assert "202" not in group_reply.text
        assert (await session.execute(select(TelegramAccessGrant).where(TelegramAccessGrant.telegram_user_id == 202))).scalar_one().active

    async with session_scope() as session:
        await ingress.accept(session, message("private-remove", 101, 101, "/removeuser 202"))
    assert await inbox_worker.process_one(deps)
    async with session_scope() as session:
        assert not (await session.execute(select(TelegramAccessGrant).where(TelegramAccessGrant.telegram_user_id == 202))).scalar_one().active

    # Revoked users are dropped before journal resolution or mutation.
    async with session_scope() as session:
        await ingress.accept(session, message("revoked-user", 202, 202, "dinner"))
    assert await inbox_worker.process_one(deps)
    assert journal.calls == [202, 101]
