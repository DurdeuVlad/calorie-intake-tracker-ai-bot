from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import OpenFoodFactsLookupCache


async def find(session: AsyncSession, cache_key: str) -> OpenFoodFactsLookupCache | None:
    return (await session.execute(select(OpenFoodFactsLookupCache).where(OpenFoodFactsLookupCache.cache_key == cache_key))).scalar_one_or_none()
