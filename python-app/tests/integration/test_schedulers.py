import uuid
from datetime import UTC, datetime, time, timedelta

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
async def test_boundary_reminder_fires_once_within_the_lead_window_and_is_idempotent():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1006, "Tester", "Europe/Bucharest")
        settings = await _reload_settings(session, user.id)
        settings.onboarding_completed = True
        settings.reports_enabled = True
        settings.day_boundary_hour = 4
        settings.day_boundary_reminder_enabled = True
        session.add(MessagingRoute(user_id=user.id, provider="telegram", conversation_id="1006"))
        await session.commit()

    # 03:30 Europe/Bucharest (UTC+3 in June) -- 30 minutes before the 4am
    # boundary, inside the 60-minute lead window.
    fixed_now = datetime(2026, 6, 15, 0, 30, tzinfo=UTC)
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
        outbound = (await session.execute(select(MessagingOutboundMessage).where(MessagingOutboundMessage.conversation_id == "1006"))).scalars().all()

    boundary_deliveries = [d for d in deliveries if d.report_type == "day_boundary"]
    assert len(boundary_deliveries) == 1  # claimed exactly once despite 3 ticks
    assert len(outbound) == 1
    assert "4" in outbound[0].text


@pytest.mark.asyncio
async def test_boundary_reminder_does_not_fire_outside_the_lead_window():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1007, "Tester", "Europe/Bucharest")
        settings = await _reload_settings(session, user.id)
        settings.onboarding_completed = True
        settings.reports_enabled = True
        settings.day_boundary_hour = 4
        settings.day_boundary_reminder_enabled = True
        await session.commit()

    # Noon local -- nowhere near the 4am boundary.
    fixed_now = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
    assert [d for d in deliveries if d.report_type == "day_boundary"] == []


@pytest.mark.asyncio
async def test_boundary_reminder_requires_opt_in():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1008, "Tester", "Europe/Bucharest")
        settings = await _reload_settings(session, user.id)
        settings.onboarding_completed = True
        settings.reports_enabled = True
        settings.day_boundary_hour = 4
        # day_boundary_reminder_enabled defaults to False -- leave it as-is.
        await session.commit()

    fixed_now = datetime(2026, 6, 15, 0, 30, tzinfo=UTC)  # inside the lead window
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
    assert [d for d in deliveries if d.report_type == "day_boundary"] == []


@pytest.mark.asyncio
async def test_tracking_nudge_fires_for_a_user_who_has_never_logged_anything():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1009, "Tester", "Europe/Bucharest")
        settings = await _reload_settings(session, user.id)
        settings.onboarding_completed = True
        settings.reports_enabled = True
        settings.tracking_nudge_enabled = True
        # Push the morning/evening report times past this test's fixed_now (noon)
        # so only the nudge fires -- reports_enabled must stay True since it's
        # the master switch _maybe_send_tracking_nudge is gated behind too.
        settings.morning_report_time = time(23, 0)
        settings.evening_report_time = time(23, 30)
        session.add(MessagingRoute(user_id=user.id, provider="telegram", conversation_id="1009"))
        await session.commit()

    # Noon Europe/Bucharest (UTC+3 in June) -- well inside waking hours.
    fixed_now = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)  # idempotent

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
        outbound = (await session.execute(select(MessagingOutboundMessage).where(MessagingOutboundMessage.conversation_id == "1009"))).scalars().all()
    assert len([d for d in deliveries if d.report_type == "nudge"]) == 1
    assert len(outbound) == 1


@pytest.mark.asyncio
async def test_tracking_nudge_does_not_fire_during_quiet_hours():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1010, "Tester", "Europe/Bucharest")
        settings = await _reload_settings(session, user.id)
        settings.onboarding_completed = True
        settings.reports_enabled = True
        settings.tracking_nudge_enabled = True
        await session.commit()

    # 23:00 Europe/Bucharest (UTC+3 in June) -- inside the quiet-hours window.
    fixed_now = datetime(2026, 6, 15, 20, 0, tzinfo=UTC)
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
    assert [d for d in deliveries if d.report_type == "nudge"] == []


@pytest.mark.asyncio
async def test_tracking_nudge_does_not_fire_with_a_recent_entry():
    from app.db.models.entries import FoodEntry

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1011, "Tester", "Europe/Bucharest")
        settings = await _reload_settings(session, user.id)
        settings.onboarding_completed = True
        settings.reports_enabled = True
        settings.tracking_nudge_enabled = True
        recent = datetime(2026, 6, 15, 11, 0, tzinfo=UTC)  # 1 hour before fixed_now below
        session.add(FoodEntry(user_id=user.id, original_message="cafea", eaten_at=recent, calories=50, nutrition_source="manual", confidence="high", created_at=recent))
        await session.commit()

    fixed_now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)  # only 1h since the entry above, under the 6h threshold
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
    assert [d for d in deliveries if d.report_type == "nudge"] == []


@pytest.mark.asyncio
async def test_tracking_nudge_requires_opt_in():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1012, "Tester", "Europe/Bucharest")
        settings = await _reload_settings(session, user.id)
        settings.onboarding_completed = True
        settings.reports_enabled = True
        # tracking_nudge_enabled defaults to False -- leave it as-is.
        await session.commit()

    fixed_now = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)
    await report_scheduler.deliver_due_reports(now_fn=lambda: fixed_now)

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
    assert [d for d in deliveries if d.report_type == "nudge"] == []


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


@pytest.mark.asyncio
async def test_pinned_status_dispatcher_unpins_the_replaced_message_when_editing_fails():
    """A failed edit falls back to sending a replacement message. Telegram
    surfaces the pinned message with the latest send date, not the latest
    pin action, so an orphaned old pin can outrank the fresh one -- the
    dispatcher must unpin it, not just pin the replacement."""

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1006, "Tester", "Europe/Bucharest")
        await session.commit()
        await daily_status_service.refresh(session, user, 1006)
        await session.commit()
        status = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user.id))).scalar_one()
        status.telegram_message_id = 845
        await session.commit()

    class ReplacingTelegram:
        def __init__(self):
            self.sent = []
            self.pinned = []
            self.unpinned = []

        async def edit(self, conversation_id, message_id, text):
            raise RuntimeError("message to edit not found")

        async def send(self, conversation_id, text):
            self.sent.append((conversation_id, text))
            return "1422"

        async def unpin(self, conversation_id, message_id):
            self.unpinned.append((conversation_id, message_id))

        async def pin(self, conversation_id, message_id):
            self.pinned.append((conversation_id, message_id))

    telegram = ReplacingTelegram()
    assert await pinned_status_dispatcher.dispatch_once(telegram) is True

    assert telegram.sent == [("1006", "Today: 0 entries, 0 kcal logged.")]
    assert telegram.unpinned == [("1006", "845")]
    assert telegram.pinned == [("1006", "1422")]

    async with session_scope() as session:
        status = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user.id))).scalar_one()
        assert status.telegram_message_id == 1422
        assert status.delivered_version == status.desired_version


@pytest.mark.asyncio
async def test_pinned_status_dispatcher_delivery_survives_a_failed_unpin_of_the_replaced_message():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 1007, "Tester", "Europe/Bucharest")
        await session.commit()
        await daily_status_service.refresh(session, user, 1007)
        await session.commit()
        status = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user.id))).scalar_one()
        status.telegram_message_id = 845
        await session.commit()

    class UnpinFailsTelegram:
        def __init__(self):
            self.pinned = []

        async def edit(self, conversation_id, message_id, text):
            raise RuntimeError("message to edit not found")

        async def send(self, conversation_id, text):
            return "1422"

        async def unpin(self, conversation_id, message_id):
            raise RuntimeError("simulated unpin failure")

        async def pin(self, conversation_id, message_id):
            self.pinned.append((conversation_id, message_id))

    telegram = UnpinFailsTelegram()
    assert await pinned_status_dispatcher.dispatch_once(telegram) is True
    assert telegram.pinned == [("1007", "1422")]

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
