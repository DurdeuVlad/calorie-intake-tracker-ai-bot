"""Once-a-minute report cron, ported from ReportScheduler.java. The due-check
re-evaluates every tick and is NOT itself the idempotency guard -- the
report_deliveries unique-constraint claim() is -- so re-firing this method
repeatedly is safe. The pre-2am catch-up window re-attempts BOTH of
yesterday's reports on every tick before 02:00 local, covering a scheduler
that was down across a user's report time."""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import session_scope
from app.db.models.messaging import MessagingOutboundMessage, MessagingRoute
from app.db.models.users import UserSettings
from app.repositories import food_entry_repo, report_delivery_repo

logger = logging.getLogger(__name__)

_CATCH_UP_CUTOFF = time(2, 0)


async def _send(session: AsyncSession, settings: UserSettings, report_type: str, local_date: date) -> None:
    claimed = await report_delivery_repo.claim(session, settings.user_id, report_type, local_date)
    if claimed == 0:
        return
    zone = ZoneInfo(settings.timezone)
    start, end = food_entry_repo.day_bounds(local_date, zone)
    from app.db.models.entries import FoodEntry

    day = (
        await session.execute(
            select(FoodEntry).where(FoodEntry.user_id == settings.user_id, FoodEntry.eaten_at >= start, FoodEntry.eaten_at < end, FoodEntry.deleted_at.is_(None))
        )
    ).scalars().all()
    calories = sum(e.calories or 0 for e in day)
    prefix = "Good morning. " if report_type == "morning" else "Daily summary: "
    text = f"{prefix}{len(day)} meals, {calories} kcal logged."

    routes = (await session.execute(select(MessagingRoute).where(MessagingRoute.user_id == settings.user_id))).scalars().all()
    for route in routes:
        session.add(MessagingOutboundMessage(provider=route.provider, conversation_id=route.conversation_id, text=text, next_attempt_at=datetime.now(UTC)))


async def deliver_due_reports(now_fn: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
    async with session_scope() as session:
        all_settings = (await session.execute(select(UserSettings))).scalars().all()
        for settings in all_settings:
            if not settings.onboarding_completed or not settings.reports_enabled:
                continue
            try:
                zone = ZoneInfo(settings.timezone)
            except Exception:  # noqa: BLE001 -- one user's bad timezone must not stop the whole tick
                logger.warning("Skipping report delivery for user_id=%s: invalid timezone %r", settings.user_id, settings.timezone)
                continue
            now = now_fn().astimezone(zone)
            if now.time() >= settings.morning_report_time:
                await _send(session, settings, "morning", now.date())
            if now.time() >= settings.evening_report_time:
                await _send(session, settings, "evening", now.date())
            if now.time() < _CATCH_UP_CUTOFF:
                previous = now.date() - timedelta(days=1)
                await _send(session, settings, "morning", previous)
                await _send(session, settings, "evening", previous)
        await session.commit()


async def run_forever(stop_event: asyncio.Event) -> None:
    """Runs once a minute, matching the Java @Scheduled(cron = "0 * * * * *")."""
    while not stop_event.is_set():
        try:
            await deliver_due_reports()
        except Exception:
            logger.exception("Report scheduler tick failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60)
        except TimeoutError:
            pass
