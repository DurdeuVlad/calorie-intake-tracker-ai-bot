from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.messaging import MessagingInboxMessage


async def lock_ready(session: AsyncSession) -> MessagingInboxMessage | None:
    """SELECT ... FOR UPDATE SKIP LOCKED, one row, respecting the retry backoff.
    Mirrors messaging_inbox's idx_messaging_inbox_ready(status, next_attempt_at, id)."""
    now = datetime.now(UTC)
    stmt = (
        select(MessagingInboxMessage)
        .where(
            or_(
                and_(MessagingInboxMessage.status == "PENDING", MessagingInboxMessage.next_attempt_at <= now),
                and_(MessagingInboxMessage.status == "IN_PROGRESS", MessagingInboxMessage.lease_expires_at <= now),
            )
        )
        .order_by(MessagingInboxMessage.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
