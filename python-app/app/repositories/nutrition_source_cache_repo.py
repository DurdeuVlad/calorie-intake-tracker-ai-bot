from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import NutritionSourceCache


async def find_by_barcode(session: AsyncSession, barcode: str) -> NutritionSourceCache | None:
    stmt = select(NutritionSourceCache).where(NutritionSourceCache.barcode == barcode)
    return (await session.execute(stmt)).scalar_one_or_none()
