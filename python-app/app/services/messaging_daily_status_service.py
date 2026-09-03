"""Provider-neutral per-turn status text, ported from MessagingDailyStatusService.java.
Distinct from the Telegram-only pinned status in daily_status_service.py."""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.messaging import MessagingDailyStatus
from app.db.models.users import FoodUser
from app.repositories import (
    food_entry_repo,
    food_user_repo,
    messaging_daily_status_repo,
)


async def refresh(session: AsyncSession, user: FoodUser, provider: str, conversation_id: str) -> None:
    settings = await food_user_repo.get_settings(session, user.id)
    zone = ZoneInfo(settings.timezone)
    today = food_entry_repo.local_tracking_date(datetime.now(zone), zone, settings.day_boundary_hour)
    start, end = food_entry_repo.day_bounds(today, zone, settings.day_boundary_hour)
    rows = await food_entry_repo.find_between(session, user, start, end)
    total = sum(r.calories or 0 for r in rows)
    text = f"Today: {len(rows)} entries, {total} kcal logged."
    if settings.calorie_target is not None:
        text += f" Minimum: {settings.calorie_target} kcal." if settings.target_mode == "min" else f" Target: {settings.calorie_target} kcal."

    existing = await messaging_daily_status_repo.find_by_user_and_route(session, user, provider, conversation_id)
    if existing is not None:
        existing.request(text)
    else:
        session.add(MessagingDailyStatus(user_id=user.id, provider=provider, conversation_id=conversation_id, text=text))
