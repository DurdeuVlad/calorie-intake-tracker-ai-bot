from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entries import FoodEntry, FoodItem


async def find_by_entry(session: AsyncSession, entry: FoodEntry) -> list[FoodItem]:
    stmt = select(FoodItem).where(FoodItem.entry_id == entry.id).order_by(FoodItem.id)
    return list((await session.execute(stmt)).scalars().all())


async def delete_by_entry(session: AsyncSession, entry: FoodEntry) -> None:
    await session.execute(delete(FoodItem).where(FoodItem.entry_id == entry.id))
