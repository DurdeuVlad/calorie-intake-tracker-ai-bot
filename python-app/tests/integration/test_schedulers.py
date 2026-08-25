import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.base import session_scope
from app.db.models.messaging import (
    PINNED_STATUS_MAX_BACKOFF_SECONDS,
    MessagingDailyStatus,
    MessagingOutboundMessage,
    MessagingRoute,
    PinnedDailyStatus,
)
from app.db.models.reports import ReportDelivery
from app.db.models.users import UserSettings
from app.messaging import daily_status_dispatcher, pinned_status_dispatcher
from app.messaging.frontend_registry import FrontendRegistry
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.scheduling import report_scheduler
from app.services import daily_status_service, messaging_daily_status_service


async def _reload_settings(session, user_id: int) -> UserSettings:
    return (await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))).scalar_one()


@pytest.mark.asyncio
async def test_report_scheduler_is_idempotent_across_repeated_ticks_in_the_same_minute():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1001, "Tester", "Europe/Bucharest")
        settings = await _reload_settings(session, user.id)
        settings.onboarding_completed = True
        settings.reports_enabled = True
        session.add(MessagingRoute(user_id=user.id, provider="telegram", conversation_id="1001"))
        await session.commit()

    # Fixed "now" well past the default morning report time (08:00) but before evening (22:00).
    fixed_now = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)  # Europe/Bucharest is UTC+3 in June -> 12:00 local
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
        outbound = (await session.execute(select(MessagingOutboundMessage).where(MessagingOutboundMessage.conversation_id == "1001"))).scalars().all()

    morning_deliveries = [d for d in deliveries if d.report_type == "morning"]
    assert len(morning_deliveries) == 1  # claimed exactly once despite 3 ticks
    assert len(outbound) == 1


@pytest.mark.asyncio
async def test_report_scheduler_catch_up_window_sends_yesterdays_missed_report():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1002, "Tester", "Europe/Bucharest")
        settings = await _reload_settings(session, user.id)
        settings.onboarding_completed = True
        settings.reports_enabled = True
        session.add(MessagingRoute(user_id=user.id, provider="telegram", conversation_id="1002"))
        await session.commit()

    # 01:00 local (before the 02:00 catch-up cutoff) -- morning/evening for TODAY haven't
    # happened yet (before 08:00), but yesterday's should be caught up.
    fixed_now = datetime(2026, 6, 14, 22, 0, tzinfo=UTC)  # 01:00 Europe/Bucharest (UTC+3) on 06-15
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
    types_and_dates = {(d.report_type, d.local_date.isoformat()) for d in deliveries}
    assert ("morning", "2026-06-14") in types_and_dates
    assert ("evening", "2026-06-14") in types_and_dates


@pytest.mark.asyncio
async def test_report_scheduler_skips_disabled_or_incomplete_users():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1003, "Tester", "Europe/Bucharest")
        # onboarding_completed defaults to False -- leave it as-is.
        await session.commit()

    fixed_now = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
    assert deliveries == []


@pytest.mark.asyncio
async def test_pinned_status_dispatcher_recovers_after_a_transient_failure_without_another_message():

    class FailingTelegram:
        async def send(self, conversation_id, text):
            raise RuntimeError("simulated Telegram outage")

        async def edit(self, conversation_id, message_id, text):
            raise RuntimeError("simulated Telegram outage")

        async def pin(self, conversation_id, message_id):
            raise RuntimeError("simulated Telegram outage")

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1004, "Tester", "Europe/Bucharest")
        await session.commit()
        await daily_status_service.refresh(session, user, 1004)
        await session.commit()

    processed = await pinned_status_dispatcher.dispatch_once(FailingTelegram())
    assert processed is True

    async with session_scope() as session:
        status = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user.id))).scalar_one()
        assert status.delivered_version < status.desired_version
        assert status.status == "RETRY_1"
        assert status.updated_at > datetime.now(UTC)
        assert status.lease_token is None

    # The failure cannot spin the worker before its backoff expires.
    assert await pinned_status_dispatcher.dispatch_once(FailingTelegram()) is False

    async with session_scope() as session:
        status = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user.id))).scalar_one()
        status.updated_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    class WorkingTelegram:
        def __init__(self):
            self.sent = []
            self.pinned = []

        async def send(self, conversation_id, text):
            self.sent.append((conversation_id, text))
            return "77"

        async def edit(self, conversation_id, message_id, text):
            raise AssertionError("a recovered initial send must not edit")

        async def pin(self, conversation_id, message_id):
            self.pinned.append((conversation_id, message_id))

    telegram = WorkingTelegram()
    assert await pinned_status_dispatcher.dispatch_once(telegram) is True
    assert await pinned_status_dispatcher.dispatch_once(telegram) is False
    assert telegram.sent == [("1004", "Today: 0 entries, 0 kcal logged.")]
    assert telegram.pinned == [("1004", "77")]

    async with session_scope() as session:
        status = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user.id))).scalar_one()
        assert status.delivered_version == status.desired_version
        assert status.status == "PENDING"


def test_pinned_retry_backoff_is_capped_and_uses_persisted_attempts():
    now = datetime.now(UTC)
    token = uuid.uuid4()
    status = PinnedDailyStatus(
        user_id=1, chat_id=1, local_date=now.date(), desired_text="today", desired_version=1, delivered_version=0,
        updated_at=now, status="RETRY_8", lease_token=token, lease_expires_at=now,
    )
    status.retry(token)
    assert status.status == "RETRY_9"
    assert status.updated_at - now <= timedelta(seconds=PINNED_STATUS_MAX_BACKOFF_SECONDS + 1)
    assert status.updated_at - now >= timedelta(seconds=PINNED_STATUS_MAX_BACKOFF_SECONDS - 1)


@pytest.mark.asyncio
async def test_messaging_daily_status_service_upserts_and_marks_dirty():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1005, "Tester", "Europe/Bucharest")
        await session.commit()
        await messaging_daily_status_service.refresh(session, user, "telegram", "1005")
        await session.commit()

    async with session_scope() as session:
        status = (await session.execute(select(MessagingDailyStatus).where(MessagingDailyStatus.user_id == user.id))).scalar_one()
        assert status.dirty is True
        assert "0 entries" in status.text


class StubFrontend:
    def __init__(self):
        self.sent = []

    def provider(self):
        return "telegram"

    def enabled(self):
        return True

    def message_limit(self):
        return 4096

    async def send(self, conversation_id, text):
        self.sent.append((conversation_id, text))
        return "999"

    async def edit(self, conversation_id, message_id, text):
        pass

    async def download(self, attachment):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_daily_status_dispatcher_sends_a_dirty_status_and_clears_the_flag():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1006, "Tester", "Europe/Bucharest")
        await session.commit()
        await messaging_daily_status_service.refresh(session, user, "telegram", "1006")
        await session.commit()

    registry = FrontendRegistry([StubFrontend()])
    processed = await daily_status_dispatcher.dispatch_once(registry)
    assert processed is True

    async with session_scope() as session:
        status = (await session.execute(select(MessagingDailyStatus).where(MessagingDailyStatus.user_id == user.id))).scalar_one()
        assert status.dirty is False
        assert status.remote_message_id == "999"
