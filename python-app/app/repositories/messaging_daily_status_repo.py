from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.messaging import MessagingDailyStatus
from app.db.models.users import FoodUser


async def find_by_user_and_route(session: AsyncSession, user: FoodUser, provider: str, conversation_id: str) -> MessagingDailyStatus | None:
    stmt = select(MessagingDailyStatus).where(
        MessagingDailyStatus.user_id == user.id, MessagingDailyStatus.provider == provider, MessagingDailyStatus.conversation_id == conversation_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def lock_dirty(session: AsyncSession) -> MessagingDailyStatus | None:
    stmt = select(MessagingDailyStatus).where(MessagingDailyStatus.dirty.is_(True)).order_by(MessagingDailyStatus.id).limit(1).with_for_update(skip_locked=True)
    return (await session.execute(stmt)).scalar_one_or_none()
