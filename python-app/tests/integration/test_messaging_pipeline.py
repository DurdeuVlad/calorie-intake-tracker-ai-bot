"""End-to-end inbox -> outbox pipe test, plus the regression test for the exact
bug that started this rewrite: a failing send must respect next_attempt_at
backoff, not resend immediately on the very next dispatcher tick."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.base import session_scope
from app.messaging import ingress, inbox_worker, outbox_dispatcher
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging.inbound_message import InboundMessage
from app.db.models.messaging import MessagingOutboundMessage
from app.config import get_settings


class StubFrontend:
    def __init__(self, provider: str = "telegram", limit: int = 4096, fail: bool = False):
        self._provider = provider
        self._limit = limit
        self.fail = fail
        self.sent: list[tuple[str, str]] = []

    def provider(self) -> str:
        return self._provider

    def enabled(self) -> bool:
        return True

    def message_limit(self) -> int:
        return self._limit

    async def send(self, conversation_id: str, text: str) -> str:
        if self.fail:
            raise RuntimeError("simulated transient send failure")
        self.sent.append((conversation_id, text))
        return "1"

    async def edit(self, conversation_id: str, message_id: str, text: str) -> None:
        pass

    async def download(self, attachment):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _allow_test_user(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(type(settings), "allowed_telegram_user_id_set", property(lambda self: {"42"}))
    yield


@pytest.mark.asyncio
async def test_inbound_message_travels_through_inbox_to_outbox():
    inbound = InboundMessage(
        provider="telegram",
        event_id="evt-1",
        user_id="42",
        conversation_id="42",
        display_name="Tester",
        language_code="en",
        text="hello",
        caption=None,
    )
    async with session_scope() as session:
        await ingress.accept(session, inbound)

    processed = await inbox_worker.process_one()
    assert processed is True

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    # No agent is configured in this test, so a plain (non-slash) message falls
    # back to the canned "unavailable" reply -- see test_journal_application_service.py
    # for slash-command and onboarding coverage.
    assert any("cannot process" in r.text for r in rows)


@pytest.mark.asyncio
async def test_outbox_respects_backoff_and_does_not_resend_immediately_on_failure():
    """This is the exact regression the rewrite exists to fix: the Java sibling
    query forgot to filter PENDING rows by next_attempt_at, so any transient
    send failure caused an immediate, unbounded resend loop every ~5s. Prove the
    Python query does NOT reclaim a just-failed row before its backoff elapses."""
    failing_frontend = StubFrontend(fail=True)
    registry = FrontendRegistry([failing_frontend])

    async with session_scope() as session:
        session.add(
            MessagingOutboundMessage(
                provider="telegram", conversation_id="42", text="will fail", next_attempt_at=datetime.now(timezone.utc)
            )
        )
        await session.commit()

    processed_first = await outbox_dispatcher.dispatch_batch(registry)
    assert processed_first == 1

    async with session_scope() as session:
        row = (await session.execute(select(MessagingOutboundMessage))).scalar_one()
        assert row.status == "PENDING"
        assert row.attempts == 1
        assert row.next_attempt_at > datetime.now(timezone.utc)

    # Immediately try again -- with backoff respected, nothing should be claimed.
    processed_second = await outbox_dispatcher.dispatch_batch(registry)
    assert processed_second == 0

    # Once the backoff has elapsed, the row becomes claimable again and can succeed.
    async with session_scope() as session:
        row = (await session.execute(select(MessagingOutboundMessage))).scalar_one()
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()

    working_frontend = StubFrontend(fail=False)
    registry_ok = FrontendRegistry([working_frontend])
    processed_third = await outbox_dispatcher.dispatch_batch(registry_ok)
    assert processed_third == 1
    assert working_frontend.sent == [("42", "will fail")]

    async with session_scope() as session:
        row = (await session.execute(select(MessagingOutboundMessage))).scalar_one()
        assert row.status == "SENT"


@pytest.mark.asyncio
async def test_outbox_truncates_over_limit_text():
    long_text = "x" * 5000
    async with session_scope() as session:
        session.add(
            MessagingOutboundMessage(
                provider="telegram", conversation_id="42", text=long_text, next_attempt_at=datetime.now(timezone.utc)
            )
        )
        await session.commit()

    frontend = StubFrontend(limit=4096)
    registry = FrontendRegistry([frontend])
    await outbox_dispatcher.dispatch_batch(registry)

    assert len(frontend.sent) == 1
    sent_text = frontend.sent[0][1]
    assert len(sent_text) == 4096
    assert sent_text.endswith("[Message truncated]")
