"""Read-only queries for immutable nutrition provenance."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import NutritionEvidence


async def find_by_food_entry_ids(session: AsyncSession, entry_ids: list[int]) -> dict[int, NutritionEvidence]:
    """Return provenance indexed by entry id for a just-created receipt."""
    if not entry_ids:
        return {}
    stmt = select(NutritionEvidence).where(NutritionEvidence.food_entry_id.in_(entry_ids))
    rows = (await session.execute(stmt)).scalars().all()
    return {row.food_entry_id: row for row in rows}
