"""End-to-end inbox -> outbox pipe test, plus regression tests for the exact
bug that started this rewrite: a failing send must respect next_attempt_at
backoff, not resend immediately on the very next dispatcher tick. Also covers
the daily-status flood-control storm fix (see daily_status_dispatcher.py):
a failing daily-status edit must give up rather than be reclaimed by the very
next tick with zero backoff."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import session_scope
from app.db.models.entries import FoodEntry
from app.db.models.messaging import (
    MessagingDailyStatus,
    MessagingInboxMessage,
    MessagingOutboundMessage,
    TelegramAccessGrant,
)
from app.db.models.users import FoodUser
from app.messaging import (
    daily_status_dispatcher,
    inbox_worker,
    ingress,
    outbox,
    outbox_dispatcher,
)
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging.inbound_message import Attachment, AttachmentKind, InboundMessage
from app.telegram_bot.webhook_router import MAX_WEBHOOK_BODY_BYTES, _read_bounded_body


class _StreamingRequest:
    def __init__(self, chunks: list[bytes], content_length: str | None = None) -> None:
        self.headers = {} if content_length is None else {"content-length": content_length}
        self._chunks = chunks

    async def stream(self):
        for chunk in self._chunks:
            yield chunk


@pytest.mark.asyncio
async def test_webhook_body_reader_rejects_content_length_before_buffering():
    request = _StreamingRequest([], str(MAX_WEBHOOK_BODY_BYTES + 1))
    assert await _read_bounded_body(request) is None


@pytest.mark.asyncio
async def test_webhook_body_reader_bounds_chunked_requests():
    request = _StreamingRequest([b"x" * MAX_WEBHOOK_BODY_BYTES, b"overflow"])
    assert await _read_bounded_body(request) is None


class FailingJournal:
    default_timezone = "Europe/Bucharest"

    async def handle(self, session, user, chat_id, message, **kwargs):
        session.add(
            FoodEntry(
                user_id=user.id,
                original_message="should roll back",
                eaten_at=datetime.now(UTC),
                calories=999,
                nutrition_source="manual",
                confidence="high",
                created_at=datetime.now(UTC),
            )
        )
        await session.flush()
        raise RuntimeError("simulated journal failure")


class DatabaseFailingJournal:
    default_timezone = "Europe/Bucharest"

    async def handle(self, session, user, chat_id, message, **kwargs):
        session.add(
            FoodEntry(
                user_id=user.id,
                original_message="should roll back database failure",
                eaten_at=datetime.now(UTC),
                calories=999,
                nutrition_source="manual",
                confidence="high",
                created_at=datetime.now(UTC),
            )
        )
        await session.flush()
        raise IntegrityError("simulated serialization failure", {}, RuntimeError("serialization failure"))


class SuccessfulJournal:
    default_timezone = "Europe/Bucharest"

    def __init__(self, original_message: str = "should persist once") -> None:
        self.original_message = original_message

    async def handle(self, session, user, chat_id, message, **kwargs):
        session.add(
            FoodEntry(
                user_id=user.id,
                original_message=self.original_message,
                eaten_at=datetime.now(UTC),
                calories=321,
                nutrition_source="manual",
                confidence="high",
                created_at=datetime.now(UTC),
            )
        )
        await session.flush()
        return "Logged once."


class RecordingJournal:
    default_timezone = "Europe/Bucharest"

    def __init__(self) -> None:
        self.started_at = None

    async def handle(self, session, user, chat_id, message, **kwargs):
        self.started_at = kwargs["started_at"]
        return "Recorded."


class StubFrontend:
    def __init__(self, provider: str = "telegram", limit: int = 4096, fail: bool = False):
        self._provider = provider
        self._limit = limit
        self.fail = fail
        self.sent: list[tuple[str, str]] = []
        self.typing: list[str] = []

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

    async def send_typing(self, conversation_id: str) -> None:
        self.typing.append(conversation_id)

    async def edit(self, conversation_id: str, message_id: str, text: str) -> None:
        pass

    async def download(self, attachment):
        raise NotImplementedError


@pytest_asyncio.fixture(autouse=True)
async def _allow_test_user(monkeypatch):
    """Exercise the durable access policy with an explicitly granted account."""
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_frontend_enabled", True)
    now = datetime.now(UTC)
    async with session_scope() as session:
        session.add(
            TelegramAccessGrant(
                telegram_user_id=42,
                is_admin=False,
                active=True,
                granted_by=None,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    yield


def test_deserialize_accepts_v16_legacy_inbox_payload_shape():
    payload = json.dumps(
        {
            "provider": "telegram",
            "eventId": "legacy-event",
            "userId": "42",
            "conversationId": "-10042",
            "displayName": "Legacy User",
            "languageCode": "en",
            "text": "legacy meal",
            "caption": None,
            "attachments": [
                {
                    "kind": "DOCUMENT",
                    "handle": "legacy-file",
                    "mimeType": "text/plain",
                    "name": "meal.txt",
                }
            ],
        }
    )

    message = ingress.deserialize(payload)

    assert message.event_id == "legacy-event"
    assert message.user_id == "42"
    assert message.conversation_id == "-10042"
    assert message.display_name == "Legacy User"
    assert message.attachments[0].mime_type == "text/plain"
    assert message.attachments[0].file_name == "meal.txt"


def test_deserialize_rejects_conflicting_current_and_legacy_fields():
    payload = json.dumps(
        {
            "provider": "telegram",
            "event_id": "current-event",
            "eventId": "different-event",
            "user_id": "42",
            "conversation_id": "42",
            "attachments": [],
        }
    )

    with pytest.raises(ingress.InboundPayloadError):
        ingress.deserialize(payload)


def test_deserialize_rejects_oversized_and_unbounded_inbox_fields():
    base = {
        "provider": "terminal",
        "event_id": "event",
        "user_id": "42",
        "conversation_id": "42",
        "text": "hello",
        "attachments": [],
    }

    oversized_text = {**base, "text": "x" * 4097}
    oversized_payload = {**base, "event_id": "x" * 256}
    too_many_attachments = {
        **base,
        "attachments": [{"kind": "DOCUMENT", "handle": str(index)} for index in range(5)],
    }

    for value in (oversized_text, oversized_payload, too_many_attachments):
        with pytest.raises(ingress.InboundPayloadError):
            ingress.deserialize(json.dumps(value))

    mattermost = {
        **base,
        "provider": "mattermost",
        "user_id": "1q7y3nrqtfyzigy5xryy6pd9ba",
        "conversation_id": "1q7y3nrqtfyzigy5xryy6pd9ba",
    }
    assert ingress.deserialize(json.dumps(mattermost)).user_id == mattermost["user_id"]


def test_deserialize_rejects_deeply_nested_malformed_json():
    with pytest.raises(ingress.InboundPayloadError):
        ingress.deserialize("[" * 5000 + "]" * 5000)


@pytest.mark.asyncio
async def test_accept_rejects_invalid_messages_before_persisting_them():
    attachment = Attachment(AttachmentKind.DOCUMENT, "file", None)
    invalid_messages = [
        InboundMessage(
            provider="terminal",
            event_id="evt-oversized-live-message",
            user_id="42",
            conversation_id="42",
            display_name="Tester",
            language_code=None,
            text="x" * 4097,
            caption=None,
        ),
        InboundMessage(
            provider="terminal",
            event_id="evt-too-many-live-attachments",
            user_id="42",
            conversation_id="42",
            display_name="Tester",
            language_code=None,
            text=None,
            caption=None,
            attachments=[attachment] * 5,
        ),
    ]

    async with session_scope() as session:
        for message in invalid_messages:
            assert await ingress.accept(session, message) is False

    async with session_scope() as session:
        rows = (
            await session.execute(
                select(MessagingInboxMessage).where(
                    MessagingInboxMessage.event_id.in_(message.event_id for message in invalid_messages)
                )
            )
        ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_legacy_inbox_payload_is_processed_through_the_worker():
    payload = json.dumps(
        {
            "provider": "telegram",
            "eventId": "legacy-worker-event",
            "userId": "42",
            "conversationId": "42",
            "displayName": "Legacy User",
            "languageCode": "en",
            "text": "/help",
            "caption": None,
            "attachments": [],
        }
    )
    async with session_scope() as session:
        session.add(
            MessagingInboxMessage(
                provider="telegram",
                event_id="legacy-worker-event",
                payload=payload,
                next_attempt_at=datetime.now(UTC),
            )
        )
        await session.commit()

    processed = await inbox_worker.process_one(
        inbox_worker.InboxWorkerDeps(
            journal=inbox_worker.JournalApplicationService(get_settings().default_timezone),
            frontends=FrontendRegistry([StubFrontend()]),
        )
    )
    assert processed is True

    async with session_scope() as session:
        row = (
            await session.execute(
                select(MessagingInboxMessage).where(MessagingInboxMessage.event_id == "legacy-worker-event")
            )
        ).scalar_one()
    assert row.status == "COMPLETED"
    assert row.payload == ""


@pytest.mark.asyncio
async def test_worker_passes_persisted_received_at_to_journal():
    received_at = datetime(2024, 1, 31, 23, 59, tzinfo=UTC)
    payload = json.dumps(
        {
            "provider": "terminal",
            "event_id": "evt-received-at",
            "user_id": "9005",
            "conversation_id": "9005",
            "display_name": "Timestamp Tester",
            "language_code": "en",
            "text": "timestamped meal",
            "caption": None,
            "attachments": [],
        }
    )
    journal = RecordingJournal()
    async with session_scope() as session:
        session.add(
            MessagingInboxMessage(
                provider="terminal",
                event_id="evt-received-at",
                payload=payload,
                received_at=received_at,
                next_attempt_at=datetime.now(UTC),
            )
        )
        await session.commit()

    assert await inbox_worker.process_one(
        inbox_worker.InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([]))
    ) is True
    assert journal.started_at == received_at


@pytest.mark.asyncio
async def test_inbox_commit_failure_persists_retry_state_in_recovery_transaction(monkeypatch):
    inbound = InboundMessage(
        provider="terminal",
        event_id="evt-commit-failure",
        user_id="9006",
        conversation_id="9006",
        display_name="Commit Failure Tester",
        language_code="en",
        text="commit failure",
        caption=None,
    )
    async with session_scope() as session:
        await ingress.accept(session, inbound)

    original_commit = AsyncSession.commit
    calls = 0

    async def fail_once(session):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated inbox commit failure")
        await original_commit(session)

    monkeypatch.setattr(AsyncSession, "commit", fail_once)
    assert await inbox_worker.process_one(
        inbox_worker.InboxWorkerDeps(journal=SuccessfulJournal("commit failure"), frontends=FrontendRegistry([]))
    ) is True

    async with session_scope() as session:
        row = (
            await session.execute(
                select(MessagingInboxMessage).where(MessagingInboxMessage.event_id == "evt-commit-failure")
            )
        ).scalar_one()

    assert calls == 2
    assert row.status == "PENDING"
    assert row.attempts == 1
    assert row.next_attempt_at > datetime.now(UTC)


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

    frontend = StubFrontend()
    # The worker gives Telegram immediate visual feedback before producing the
    # durable final response; dispatcher delivery remains a separate step.
    processed = await inbox_worker.process_one(
        inbox_worker.InboxWorkerDeps(journal=inbox_worker.JournalApplicationService(get_settings().default_timezone), frontends=FrontendRegistry([frontend]))
    )
    assert processed is True
    assert frontend.typing == ["42"]

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    # No agent is configured in this test, so a plain (non-slash) message falls
    # back to the canned "unavailable" reply in the user's preferred_language
    # (default "ro" for new users) -- see test_journal_application_service.py
    # for slash-command and onboarding coverage.
    assert any("cannot process" in r.text or "Nu pot procesa" in r.text for r in rows)


@pytest.mark.asyncio
async def test_unexpected_journal_failure_rolls_back_business_changes_but_retries_inbox():
    inbound = InboundMessage(
        provider="terminal",
        event_id="evt-rollback",
        user_id="9001",
        conversation_id="9001",
        display_name="Failure Tester",
        language_code="en",
        text="trigger failure",
        caption=None,
    )
    async with session_scope() as session:
        await ingress.accept(session, inbound)

    processed = await inbox_worker.process_one(
        inbox_worker.InboxWorkerDeps(journal=FailingJournal(), frontends=FrontendRegistry([]))
    )
    assert processed is True

    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.original_message == "should roll back"))).scalars().all()
        inbox = (await session.execute(select(MessagingInboxMessage).where(MessagingInboxMessage.event_id == "evt-rollback"))).scalar_one()

    assert entries == []
    assert inbox.status == "PENDING"
    assert inbox.attempts == 1


@pytest.mark.asyncio
async def test_database_failure_persists_retry_state_in_a_fresh_transaction():
    inbound = InboundMessage(
        provider="terminal",
        event_id="evt-database-failure",
        user_id="9004",
        conversation_id="9004",
        display_name="Database Failure Tester",
        language_code="en",
        text="trigger database failure",
        caption=None,
    )
    async with session_scope() as session:
        await ingress.accept(session, inbound)

    processed = await inbox_worker.process_one(
        inbox_worker.InboxWorkerDeps(journal=DatabaseFailingJournal(), frontends=FrontendRegistry([]))
    )
    assert processed is True

    async with session_scope() as session:
        entries = (
            await session.execute(
                select(FoodEntry).where(FoodEntry.original_message == "should roll back database failure")
            )
        ).scalars().all()
        inbox = (
            await session.execute(
                select(MessagingInboxMessage).where(MessagingInboxMessage.event_id == "evt-database-failure")
            )
        ).scalar_one()

    assert entries == []
    assert inbox.status == "PENDING"
    assert inbox.attempts == 1


@pytest.mark.asyncio
async def test_post_journal_bookkeeping_failures_do_not_retry_the_mutation(monkeypatch):
    inbound = InboundMessage(
        provider="terminal",
        event_id="evt-post-journal-failure",
        user_id="9002",
        conversation_id="9002",
        display_name="Bookkeeping Tester",
        language_code="en",
        text="persist once",
        caption=None,
    )
    async with session_scope() as session:
        await ingress.accept(session, inbound)

    async def fail_record_turn(*args, **kwargs):
        raise RuntimeError("simulated memory failure")

    async def fail_daily_status(*args, **kwargs):
        raise RuntimeError("simulated status failure")

    monkeypatch.setattr(inbox_worker, "record_turn", fail_record_turn)
    monkeypatch.setattr(inbox_worker.messaging_daily_status_service, "refresh", fail_daily_status)

    processed = await inbox_worker.process_one(
        inbox_worker.InboxWorkerDeps(journal=SuccessfulJournal(), frontends=FrontendRegistry([]))
    )
    assert processed is True

    async with session_scope() as session:
        entries = (
            await session.execute(select(FoodEntry).where(FoodEntry.original_message == "should persist once"))
        ).scalars().all()
        inbox = (
            await session.execute(
                select(MessagingInboxMessage).where(MessagingInboxMessage.event_id == "evt-post-journal-failure")
            )
        ).scalar_one()
        replies = (
            await session.execute(
                select(MessagingOutboundMessage).where(
                    MessagingOutboundMessage.conversation_id == "9002",
                    MessagingOutboundMessage.text == "Logged once.",
                )
            )
        ).scalars().all()

    assert len(entries) == 1
    assert inbox.status == "COMPLETED"
    assert inbox.attempts == 0
    assert len(replies) == 1


@pytest.mark.asyncio
async def test_outbox_persistence_failure_rolls_back_before_retry(monkeypatch):
    inbound = InboundMessage(
        provider="terminal",
        event_id="evt-outbox-failure",
        user_id="9003",
        conversation_id="9003",
        display_name="Outbox Tester",
        language_code="en",
        text="persist after retry",
        caption=None,
    )
    async with session_scope() as session:
        await ingress.accept(session, inbound)

    original_reply = inbox_worker.outbox.reply
    calls = 0

    async def fail_once(session, provider, conversation_id, text):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated outbox persistence failure")
        await original_reply(session, provider, conversation_id, text)

    monkeypatch.setattr(inbox_worker.outbox, "reply", fail_once)
    deps = inbox_worker.InboxWorkerDeps(
        journal=SuccessfulJournal("should persist after retry"), frontends=FrontendRegistry([])
    )

    assert await inbox_worker.process_one(deps) is True
    async with session_scope() as session:
        first_entries = (
            await session.execute(select(FoodEntry).where(FoodEntry.original_message == "should persist after retry"))
        ).scalars().all()
        first_inbox = (
            await session.execute(
                select(MessagingInboxMessage).where(MessagingInboxMessage.event_id == "evt-outbox-failure")
            )
        ).scalar_one()
        first_inbox.next_attempt_at = datetime.now(UTC)
        await session.commit()
    assert first_entries == []
    assert first_inbox.status == "PENDING"

    assert await inbox_worker.process_one(deps) is True
    async with session_scope() as session:
        entries = (
            await session.execute(select(FoodEntry).where(FoodEntry.original_message == "should persist after retry"))
        ).scalars().all()
        inbox = (
            await session.execute(
                select(MessagingInboxMessage).where(MessagingInboxMessage.event_id == "evt-outbox-failure")
            )
        ).scalar_one()
    assert len(entries) == 1
    assert inbox.status == "COMPLETED"
    assert calls == 2


@pytest.mark.asyncio
async def test_outbox_wake_signal_releases_idle_dispatcher_without_polling_delay():
    outbox.begin_dispatch_cycle()
    waiter = asyncio.create_task(outbox.wait_for_dispatch(30))
    await asyncio.sleep(0)
    outbox.request_dispatch()
    await asyncio.wait_for(waiter, timeout=0.1)


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
                provider="telegram", conversation_id="42", text="will fail", next_attempt_at=datetime.now(UTC)
            )
        )
        await session.commit()

    processed_first = await outbox_dispatcher.dispatch_batch(registry)
    assert processed_first == 1

    async with session_scope() as session:
        row = (await session.execute(select(MessagingOutboundMessage))).scalar_one()
        assert row.status == "PENDING"
        assert row.attempts == 1
        assert row.next_attempt_at > datetime.now(UTC)

    # Immediately try again -- with backoff respected, nothing should be claimed.
    processed_second = await outbox_dispatcher.dispatch_batch(registry)
    assert processed_second == 0

    # Once the backoff has elapsed, the row becomes claimable again and can succeed.
    async with session_scope() as session:
        row = (await session.execute(select(MessagingOutboundMessage))).scalar_one()
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
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
                provider="telegram", conversation_id="42", text=long_text, next_attempt_at=datetime.now(UTC)
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


@pytest.mark.asyncio
async def test_daily_status_gives_up_instead_of_looping_forever_on_failure():
    """Regression test for the production flood-control storm this fix
    addresses: a persistently failing daily-status dispatch must not be
    reclaimed by the very next dispatcher tick with zero backoff. Before this
    fix, a failed row stayed dirty forever with no lease/backoff bookkeeping,
    so run_forever() never slept between attempts (it only sleeps when
    nothing was claimed) -- an unbounded busy loop that exhausted the bot's
    global Telegram rate limit and delayed delivery for every other chat."""
    async with session_scope() as session:
        user = FoodUser(telegram_user_id=8131572669, display_name="Stuck Chat", created_at=datetime.now(UTC))
        session.add(user)
        await session.flush()
        session.add(
            MessagingDailyStatus(
                user_id=user.id, provider="telegram", conversation_id="8131572669", text="Today: 1 entry, 100 kcal logged."
            )
        )
        await session.commit()

    failing_frontend = StubFrontend(fail=True)
    registry = FrontendRegistry([failing_frontend])

    processed_first = await daily_status_dispatcher.dispatch_once(registry)
    assert processed_first is True

    async with session_scope() as session:
        row = (await session.execute(select(MessagingDailyStatus))).scalar_one()
        assert row.dirty is False  # gave up, rather than staying dirty for an immediate retry

    # Immediately try again -- with dirty cleared, nothing should be claimed.
    processed_second = await daily_status_dispatcher.dispatch_once(registry)
    assert processed_second is False

    # A fresh refresh() call (the next inbound message) marks it dirty again
    # and delivery succeeds normally once the underlying problem clears.
    working_frontend = StubFrontend(fail=False)
    registry_ok = FrontendRegistry([working_frontend])
    async with session_scope() as session:
        row = (await session.execute(select(MessagingDailyStatus))).scalar_one()
        row.request("Today: 2 entries, 250 kcal logged.")
        await session.commit()

    processed_third = await daily_status_dispatcher.dispatch_once(registry_ok)
    assert processed_third is True
    assert working_frontend.sent == [("8131572669", "Today: 2 entries, 250 kcal logged.")]


@pytest.mark.asyncio
async def test_malformed_inbox_payload_is_failed_without_retrying():
    async with session_scope() as session:
        session.add(
            MessagingInboxMessage(
                provider="terminal",
                event_id="evt-malformed-payload",
                payload="not-json",
                next_attempt_at=datetime.now(UTC),
            )
        )
        await session.commit()

    processed = await inbox_worker.process_one(
        inbox_worker.InboxWorkerDeps(journal=FailingJournal(), frontends=FrontendRegistry([]))
    )
    assert processed is True

    async with session_scope() as session:
        row = (
            await session.execute(
                select(MessagingInboxMessage).where(MessagingInboxMessage.event_id == "evt-malformed-payload")
            )
        ).scalar_one()

    assert row.status == "FAILED"
    assert row.attempts == 1
    assert row.payload == ""


@pytest.mark.asyncio
async def test_typed_malformed_inbox_payloads_are_failed_without_retrying():
    payloads = [
        {
            "provider": "telegram",
            "event_id": "evt-invalid-user-id",
            "user_id": 42,
            "conversation_id": "42",
            "text": "hello",
            "attachments": [],
        },
        {
            "provider": "unknown",
            "event_id": "evt-invalid-provider",
            "user_id": "42",
            "conversation_id": "42",
            "text": "hello",
            "attachments": [],
        },
        {
            "provider": "telegram",
            "event_id": "evt-invalid-user-id-format",
            "user_id": "not-a-number",
            "conversation_id": "42",
            "text": "hello",
            "attachments": [],
        },
        {
            "provider": "telegram",
            "event_id": "evt-invalid-conversation-id-format",
            "user_id": "42",
            "conversation_id": "not-a-number",
            "text": "hello",
            "attachments": [],
        },
        {
            "provider": "telegram",
            "event_id": "evt-invalid-attachment",
            "user_id": "42",
            "conversation_id": "42",
            "text": None,
            "attachments": [{"kind": "UNKNOWN", "handle": "file", "mime_type": None}],
        },
        {
            "provider": "telegram",
            "event_id": "evt-invalid-text",
            "user_id": "42",
            "conversation_id": "42",
            "text": 123,
            "attachments": [],
        },
    ]
    async with session_scope() as session:
        for payload in payloads:
            session.add(
                MessagingInboxMessage(
                    provider="telegram",
                    event_id=payload["event_id"],
                    payload=json.dumps(payload),
                    next_attempt_at=datetime.now(UTC),
                )
            )
        await session.commit()

    worker = inbox_worker.InboxWorkerDeps(journal=FailingJournal(), frontends=FrontendRegistry([]))
    for _ in payloads:
        assert await inbox_worker.process_one(worker) is True

    async with session_scope() as session:
        rows = (
            await session.execute(
                select(MessagingInboxMessage).where(
                    MessagingInboxMessage.event_id.in_(payload["event_id"] for payload in payloads)
                )
            )
        ).scalars().all()

    assert {row.status for row in rows} == {"FAILED"}
    assert {row.attempts for row in rows} == {1}
    assert {row.payload for row in rows} == {""}
