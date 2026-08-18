from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entries import FoodEntry
from app.db.models.users import FoodUser


def day_bounds(day: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=zone)
    return start, start + timedelta(days=1)


async def find_between(
    session: AsyncSession, user: FoodUser, start: datetime, end: datetime, include_deleted: bool = False
) -> list[FoodEntry]:
    stmt = select(FoodEntry).where(FoodEntry.user_id == user.id, FoodEntry.eaten_at >= start, FoodEntry.eaten_at < end)
    if not include_deleted:
        stmt = stmt.where(FoodEntry.deleted_at.is_(None))
    stmt = stmt.order_by(FoodEntry.eaten_at.asc())
    return list((await session.execute(stmt)).scalars().all())


async def today_totals(session: AsyncSession, user: FoodUser, timezone_name: str, today: date) -> tuple[int, int]:
    """Returns (calories, entry_count) for the given local date."""
    zone = ZoneInfo(timezone_name)
    start, end = day_bounds(today, zone)
    rows = await find_between(session, user, start, end)
    calories = sum(r.calories or 0 for r in rows)
    return calories, len(rows)


async def find_by_id_and_user(session: AsyncSession, entry_id: int, user: FoodUser, include_deleted: bool = False) -> FoodEntry | None:
    stmt = select(FoodEntry).where(FoodEntry.id == entry_id, FoodEntry.user_id == user.id)
    if not include_deleted:
        stmt = stmt.where(FoodEntry.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


async def search_by_term(session: AsyncSession, user: FoodUser, term: str) -> list[FoodEntry]:
    stmt = (
        select(FoodEntry)
        .where(FoodEntry.user_id == user.id, FoodEntry.deleted_at.is_(None), func.lower(FoodEntry.original_message).contains(term.lower()))
        .order_by(FoodEntry.eaten_at.asc())
    )
    return list((await session.execute(stmt)).scalars().all())
