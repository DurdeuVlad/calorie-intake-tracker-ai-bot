import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import PendingNutritionQuote
from app.db.models.users import FoodUser


async def lock_owned_active(session: AsyncSession, quote_id: uuid.UUID, user: FoodUser, now: datetime) -> PendingNutritionQuote | None:
    stmt = (
        select(PendingNutritionQuote)
        .where(PendingNutritionQuote.quote_id == quote_id, PendingNutritionQuote.user_id == user.id, PendingNutritionQuote.expires_at > now)
        .with_for_update()
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def find_first_by_type(
    session: AsyncSession, user: FoodUser, quote_type: str, now: datetime
) -> PendingNutritionQuote | None:
    stmt = (
        select(PendingNutritionQuote)
        .where(PendingNutritionQuote.user_id == user.id, PendingNutritionQuote.quote_type == quote_type, PendingNutritionQuote.expires_at > now)
        .order_by(PendingNutritionQuote.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def find_by_batch(session: AsyncSession, user: FoodUser, batch_id: uuid.UUID, now: datetime) -> list[PendingNutritionQuote]:
    stmt = (
        select(PendingNutritionQuote)
        .where(PendingNutritionQuote.user_id == user.id, PendingNutritionQuote.batch_id == batch_id, PendingNutritionQuote.expires_at > now)
        .order_by(PendingNutritionQuote.created_at.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def delete_quote(session: AsyncSession, quote: PendingNutritionQuote) -> None:
    await session.delete(quote)
