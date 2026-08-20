from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.conversation import ConversationMemory
from app.db.models.users import FoodUser

MAX_MESSAGES = 10


async def recent(session: AsyncSession, user: FoodUser) -> list[ConversationMemory]:
    stmt = (
        select(ConversationMemory)
        .where(ConversationMemory.user_id == user.id)
        .order_by(ConversationMemory.created_at.desc(), ConversationMemory.id.desc())
        .limit(MAX_MESSAGES)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    rows.reverse()
    return rows


async def prune_beyond_max(session: AsyncSession, user: FoodUser) -> None:
    stmt = (
        select(ConversationMemory.id)
        .where(ConversationMemory.user_id == user.id)
        .order_by(ConversationMemory.created_at.desc(), ConversationMemory.id.desc())
        .offset(MAX_MESSAGES)
    )
    stale_ids = [row[0] for row in (await session.execute(stmt)).all()]
    if stale_ids:
        await session.execute(delete(ConversationMemory).where(ConversationMemory.id.in_(stale_ids)))
