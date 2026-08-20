from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.messaging import PinnedDailyStatus
from app.db.models.users import FoodUser


async def find_by_user_and_chat_id(session: AsyncSession, user: FoodUser, chat_id: int) -> PinnedDailyStatus | None:
    stmt = select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user.id, PinnedDailyStatus.chat_id == chat_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def lock_pending(session: AsyncSession) -> PinnedDailyStatus | None:
    now = datetime.now(timezone.utc)
    stmt = (
        select(PinnedDailyStatus)
        .where(
            PinnedDailyStatus.desired_version > PinnedDailyStatus.delivered_version,
            (PinnedDailyStatus.status == "PENDING") | ((PinnedDailyStatus.status == "IN_PROGRESS") & (PinnedDailyStatus.lease_expires_at <= now)),
        )
        .order_by(PinnedDailyStatus.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()
