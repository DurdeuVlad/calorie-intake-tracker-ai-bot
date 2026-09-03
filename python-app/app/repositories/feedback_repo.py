"""Read/write path for user-submitted feedback -- stored and returned verbatim, never summarized or altered."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.feedback import UserFeedback
from app.db.models.users import FoodUser

MAX_FEEDBACK_CHARS = 2000


async def create(session: AsyncSession, user: FoodUser, source: str, message: str, now: datetime) -> UserFeedback:
    feedback = UserFeedback(user_id=user.id, source=source, message=message[:MAX_FEEDBACK_CHARS], created_at=now)
    session.add(feedback)
    await session.flush()
    return feedback


async def recent(session: AsyncSession, user: FoodUser, limit: int = 10) -> list[UserFeedback]:
    stmt = (
        select(UserFeedback)
        .where(UserFeedback.user_id == user.id)
        # id as a tiebreaker: two submissions in the same request/tick can share
        # a created_at, and created_at alone gives Postgres no stable ordering
        # for ties (same pattern as journal_change_set_repo.find_first_undoable).
        .order_by(UserFeedback.created_at.desc(), UserFeedback.id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
