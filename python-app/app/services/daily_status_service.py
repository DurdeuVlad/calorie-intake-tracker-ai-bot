"""Telegram-only PINNED daily status, ported from DailyStatusService.java. This
is distinct from MessagingDailyStatusService (provider-neutral, plain per-turn
status message) -- both exist in parallel, matching the Java predecessor."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.messaging import PinnedDailyStatus
from app.db.models.users import FoodUser
from app.repositories import food_entry_repo, food_user_repo, pinned_daily_status_repo


@dataclass(frozen=True)
class PinnedDelivery:
    id: int
    chat_id: int
    text: str
    version: int
    message_id: int | None
    lease_token: uuid.UUID


def _status_text(rows_count: int, calories: int, target: int | None) -> str:
    text = f"Today: {rows_count} entries, {calories} kcal logged."
    if target is not None:
        text += f" Target: {target} kcal."
    return text


async def refresh_for_tool_executor(session: AsyncSession, user: FoodUser, chat_id: str) -> None:
    """Adapter matching JournalToolExecutor's RefreshDailyStatus callable shape
    (chat_id as the AgentContext's str), delegating to refresh() below."""
    await refresh(session, user, int(chat_id))


async def refresh(session: AsyncSession, user: FoodUser, chat_id: int) -> None:
    # This is deliberately safe inside the live message execution context.
    # Journal mutations call it after their database changes have been flushed,
    # and the row is the durable hand-off to the Telegram dispatcher.
    settings = await food_user_repo.get_settings(session, user.id)
    zone = ZoneInfo(settings.timezone)
    today = datetime.now(zone).date()
    start, end = food_entry_repo.day_bounds(today, zone)
    rows = await food_entry_repo.find_between(session, user, start, end)
    calories = sum(r.calories or 0 for r in rows)
    text = _status_text(len(rows), calories, settings.calorie_target)

    existing = await pinned_daily_status_repo.find_by_user_and_chat_id(session, user, chat_id)
    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.request(today, text, now)
    else:
        session.add(PinnedDailyStatus(user_id=user.id, chat_id=chat_id, local_date=today, desired_text=text, desired_version=1, delivered_version=0, updated_at=now))


async def claim(session: AsyncSession) -> PinnedDelivery | None:
    status = await pinned_daily_status_repo.lock_pending(session)
    if status is None:
        return None
    status.claim()
    return PinnedDelivery(status.id, status.chat_id, status.desired_text, status.desired_version, status.telegram_message_id, status.lease_token)


async def mark_delivered(session: AsyncSession, status_id: int, version: int, token: uuid.UUID, message_id: int) -> None:
    from sqlalchemy import select

    status = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.id == status_id))).scalar_one_or_none()
    if status is not None:
        status.delivered(version, token, message_id)


async def remember_message(session: AsyncSession, status_id: int, token: uuid.UUID, message_id: int) -> None:
    from sqlalchemy import select

    status = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.id == status_id))).scalar_one_or_none()
    if status is not None:
        status.remember_message(token, message_id)


async def retry(session: AsyncSession, status_id: int, token: uuid.UUID) -> None:
    from sqlalchemy import select

    status = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.id == status_id))).scalar_one_or_none()
    if status is not None:
        status.retry(token)
