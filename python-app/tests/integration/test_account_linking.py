import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db.base import session_scope
from app.db.models.messaging import MessagingIdentity, MessagingOutboundMessage
from app.messaging import inbox_worker, ingress
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging.inbound_message import InboundMessage
from app.messaging.inbox_worker import InboxWorkerDeps
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.services import message_link_service
from app.services.journal_application_service import JournalApplicationService


@pytest.fixture(autouse=True)
def _allow_test_users(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(type(settings), "allowed_telegram_user_id_set", property(lambda self: {"501"}))
    monkeypatch.setattr(type(settings), "allowed_mattermost_user_id_set", property(lambda self: {"mm-user-1"}))
    monkeypatch.setattr(type(settings), "mattermost_enabled", property(lambda self: True))
    yield


@pytest.mark.asyncio
async def test_issue_then_redeem_links_the_mattermost_identity_to_the_same_user():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 42, "Tester", "Europe/Bucharest")
        await session.commit()
        code = await message_link_service.issue(session, user)
        await session.commit()

    async with session_scope() as session:
        linked_user = await message_link_service.redeem(session, code, "mattermost", "mm-user-1", "channel-1")
        await session.commit()
    assert linked_user.id == user.id

    async with session_scope() as session:
        identity = (await session.execute(select(MessagingIdentity).where(MessagingIdentity.provider == "mattermost", MessagingIdentity.external_user_id == "mm-user-1"))).scalar_one()
        assert identity.user_id == user.id


@pytest.mark.asyncio
async def test_redeeming_an_unknown_code_raises_link_error():
    async with session_scope() as session:
        with pytest.raises(message_link_service.LinkError):
            await message_link_service.redeem(session, "NOTAREALCODE", "mattermost", "mm-user-2", "channel-2")


@pytest.mark.asyncio
async def test_redeeming_twice_for_the_same_identity_fails_the_second_time():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 43, "Tester", "Europe/Bucharest")
        await session.commit()
        code1 = await message_link_service.issue(session, user)
        code2 = await message_link_service.issue(session, user)
        await session.commit()

    async with session_scope() as session:
        await message_link_service.redeem(session, code1, "mattermost", "mm-user-3", "channel-3")
        await session.commit()

    async with session_scope() as session:
        with pytest.raises(message_link_service.LinkError, match="already linked"):
            await message_link_service.redeem(session, code2, "mattermost", "mm-user-3", "channel-3")


@pytest.mark.asyncio
async def test_end_to_end_link_flow_through_the_inbox_worker():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([]))

    async with session_scope() as session:
        await ingress.accept(session, InboundMessage(provider="telegram", event_id="evt-link", user_id="501", conversation_id="501", display_name="Tester", language_code="en", text="/link", caption=None))
    await inbox_worker.process_one(deps)

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    reply_text = next(r.text for r in rows if "link code" in r.text)
    code = reply_text.split("link code is ")[1].split(".")[0]
    assert len(code) == 8

    async with session_scope() as session:
        await ingress.accept(session, InboundMessage(provider="mattermost", event_id="evt-redeem", user_id="mm-user-1", conversation_id="channel-1", display_name="Member", language_code=None, text=f"link {code}", caption=None))
    await inbox_worker.process_one(deps)

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    assert any("linked" in r.text for r in rows if r.conversation_id == "channel-1")

    async with session_scope() as session:
        identity = (await session.execute(select(MessagingIdentity).where(MessagingIdentity.provider == "mattermost", MessagingIdentity.external_user_id == "mm-user-1"))).scalar_one()
        telegram_identity = (await session.execute(select(MessagingIdentity).where(MessagingIdentity.provider == "telegram", MessagingIdentity.external_user_id == "501"))).scalar_one()
        assert identity.user_id == telegram_identity.user_id  # same underlying FoodUser


@pytest.mark.asyncio
async def test_invalid_link_code_via_inbox_worker_gets_a_rejection_reply():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([]))

    async with session_scope() as session:
        await ingress.accept(session, InboundMessage(provider="mattermost", event_id="evt-badcode", user_id="mm-user-1", conversation_id="channel-1", display_name="Member", language_code=None, text="link ZZZZZZZZ", caption=None))
    await inbox_worker.process_one(deps)

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    assert any("invalid, expired, or already used" in r.text for r in rows)
