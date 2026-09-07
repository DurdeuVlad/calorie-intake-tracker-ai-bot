"""Repository for user feedback records."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.feedback import UserFeedback
from app.db.models.users import FoodUser

MAX_FEEDBACK_CONTEXT = 10


async def save(
    session: AsyncSession,
    user: FoodUser,
    *,
    kind: str,
    message: str,
    context: str | None = None,
) -> UserFeedback:
    """Persist a feedback record scoped to the user."""
    record = UserFeedback(
        user_id=user.id,
        kind=kind,
        message=message,
        context=context,
        created_at=datetime.now(UTC),
    )
    session.add(record)
    await session.flush()
    return record


async def recent_for_user(
    session: AsyncSession,
    user: FoodUser,
    limit: int = 5,
) -> list[UserFeedback]:
    """Return the most recent unresolved feedback for the user, oldest first."""
    stmt = (
        select(UserFeedback)
        .where(UserFeedback.user_id == user.id, UserFeedback.resolved.is_(False))
        .order_by(UserFeedback.created_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(reversed(rows))
