from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.messaging import MessagingOutboundMessage


async def lock_ready(session: AsyncSession, limit: int = 10) -> list[MessagingOutboundMessage]:
    """SELECT ... FOR UPDATE SKIP LOCKED, up to `limit` rows, respecting the retry
    backoff. THIS IS THE EXACT QUERY WHOSE JAVA EQUIVALENT WAS MISSING THE
    `next_attempt_at` FILTER ON THE PENDING BRANCH -- that bug caused every
    transient send failure to resend the same message every ~5s forever, with no
    attempt cap, and is the whole reason this rewrite exists. The PENDING branch
    here MUST stay filtered by next_attempt_at, mirroring the inbox query exactly.
    Do not "simplify" this back to `status='PENDING' or (...)`.
    """
    now = datetime.now(UTC)
    stmt = (
        select(MessagingOutboundMessage)
        .where(
            or_(
                and_(MessagingOutboundMessage.status == "PENDING", MessagingOutboundMessage.next_attempt_at <= now),
                and_(MessagingOutboundMessage.status == "IN_PROGRESS", MessagingOutboundMessage.lease_expires_at <= now),
            )
        )
        .order_by(MessagingOutboundMessage.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
