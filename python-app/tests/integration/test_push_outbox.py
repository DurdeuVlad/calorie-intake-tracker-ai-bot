"""push_outbox drain tests: happy path, bounded retry backoff, poison ->
failed, and cancelled rows left alone. The send function is injected -- these
tests exercise the seam exactly the way a real FCM/APNs provider will."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.base import session_scope
from app.db.models.auth import AuthAccount
from app.db.models.devices import PUSH_MAX_ATTEMPTS, PushOutboxMessage
from app.db.models.users import FoodUser
from app.mobile import push as push_module
from app.repositories import push_outbox_repo


class FakeSender:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[int] = []

    async def __call__(self, row: PushOutboxMessage) -> None:
        self.calls.append(row.id)
        if self.fail:
            raise RuntimeError("simulated provider outage")


async def _account() -> int:
    """Drain tests don't need the HTTP surface -- just a real auth_accounts row
    to hang push_outbox.account_id on."""
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        user = FoodUser(telegram_user_id=None, display_name=None, created_at=now)
        session.add(user)
        await session.flush()
        account = AuthAccount(
            email=f"push-{user.id}@example.com",
            password_hash=None,
            food_user_id=user.id,
            created_at=now,
            updated_at=now,
        )
        session.add(account)
        await session.commit()
        return account.id


async def _enqueue(account_id: int, **overrides) -> int:
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        row = await push_outbox_repo.enqueue(
            session,
            account_id,
            overrides.pop("kind", "reminder"),
            overrides.pop("payload", {"title": "time to log lunch"}),
            now,
        )
        for key, value in overrides.items():
            setattr(row, key, value)
        await session.commit()
        return row.id


async def _fetch(row_id: int) -> PushOutboxMessage:
    async with session_scope() as session:
        row = (await session.execute(select(PushOutboxMessage).where(PushOutboxMessage.id == row_id))).scalar_one()
        await session.refresh(row)
        session.expunge(row)
        return row


async def _drain(sender) -> int:
    async with session_scope() as session:
        processed = await push_module.drain_push_outbox(session, sender)
        await session.commit()
        return processed


async def _make_due(row_id: int) -> None:
    async with session_scope() as session:
        row = await session.get(PushOutboxMessage, row_id)
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()


@pytest.mark.asyncio
async def test_drain_sends_due_pending_row_and_marks_it_sent():
    account_id = await _account()
    row_id = await _enqueue(account_id)
    sender = FakeSender()

    processed = await _drain(sender)

    assert processed == 1
    assert sender.calls == [row_id]
    row = await _fetch(row_id)
    assert row.status == "sent"
    assert row.sent_at is not None
    assert row.attempts == 0


@pytest.mark.asyncio
async def test_not_yet_due_row_is_not_claimed():
    account_id = await _account()
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    row_id = await _enqueue(account_id, next_attempt_at=future)
    sender = FakeSender()

    assert await _drain(sender) == 0
    assert sender.calls == []
    assert (await _fetch(row_id)).status == "pending"


@pytest.mark.asyncio
async def test_sender_failure_retries_with_backoff_not_immediately():
    account_id = await _account()
    row_id = await _enqueue(account_id)
    failing = FakeSender(fail=True)

    assert await _drain(failing) == 1
    row = await _fetch(row_id)
    assert row.status == "pending"
    assert row.attempts == 1
    assert row.next_attempt_at > datetime.now(timezone.utc)

    # Backoff is still running: the next tick must not reclaim the row.
    assert await _drain(failing) == 0
    assert failing.calls == [row_id]

    # Once the backoff elapses the row becomes claimable and can succeed.
    await _make_due(row_id)
    working = FakeSender()
    assert await _drain(working) == 1
    row = await _fetch(row_id)
    assert row.status == "sent"
    assert working.calls == [row_id]


@pytest.mark.asyncio
async def test_poison_row_marks_failed_after_max_attempts():
    account_id = await _account()
    row_id = await _enqueue(account_id)
    failing = FakeSender(fail=True)

    for attempt in range(1, PUSH_MAX_ATTEMPTS + 1):
        await _make_due(row_id)
        assert await _drain(failing) == 1
        row = await _fetch(row_id)
        assert row.attempts == attempt
        assert row.status == ("failed" if attempt == PUSH_MAX_ATTEMPTS else "pending")

    calls_before = len(failing.calls)
    await _make_due(row_id)
    assert await _drain(failing) == 0
    assert len(failing.calls) == calls_before


@pytest.mark.asyncio
async def test_cancelled_rows_are_skipped():
    account_id = await _account()
    row_id = await _enqueue(account_id, status="cancelled")
    sender = FakeSender()

    assert await _drain(sender) == 0
    assert sender.calls == []
    assert (await _fetch(row_id)).status == "cancelled"


@pytest.mark.asyncio
async def test_default_sender_is_a_stub_that_logs(caplog):
    """The seam must work with no provider wired: the default sender logs and
    reports success so enqueued rows drain instead of wedging the queue."""
    account_id = await _account()
    row_id = await _enqueue(account_id)

    async with session_scope() as session:
        with caplog.at_level("INFO", logger=push_module.logger.name):
            processed = await push_module.drain_push_outbox(session)
        await session.commit()

    assert processed == 1
    assert f"outbox_id={row_id}" in caplog.text
    assert (await _fetch(row_id)).status == "sent"
