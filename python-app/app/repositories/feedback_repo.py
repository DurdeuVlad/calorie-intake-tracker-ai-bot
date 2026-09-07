"""Repository for user feedback records."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.feedback import UserFeedback
from app.db.models.users import FoodUser

MAX_FEEDBACK_CHARS = 2000


async def save(
    session: AsyncSession,
    user: FoodUser,
    *,
    kind: str,
    message: str,
    context: str | None = None,
    source: str = "ai_detected",
    now: datetime | None = None,
) -> UserFeedback:
    """Persist a feedback record scoped to the user."""
    record = UserFeedback(
        user_id=user.id,
        kind=kind,
        source=source,
        message=message[:MAX_FEEDBACK_CHARS],
        context=context,
        created_at=now or datetime.now(UTC),
    )
    session.add(record)
    await session.flush()
    return record


async def create(session: AsyncSession, user: FoodUser, source: str, message: str, now: datetime) -> UserFeedback:
    """Backward-compatible API for the /feedback command path."""
    return await save(session, user, kind="bug", message=message, source=source, now=now)


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


async def recent(session: AsyncSession, user: FoodUser, limit: int = 10) -> list[UserFeedback]:
    """Return recent feedback (all, not just unresolved) — used for agent recall."""
    stmt = (
        select(UserFeedback)
        .where(UserFeedback.user_id == user.id)
        .order_by(UserFeedback.created_at.desc(), UserFeedback.id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
