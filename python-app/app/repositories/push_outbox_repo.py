from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.devices import PushOutboxMessage


async def enqueue(
    session: AsyncSession,
    account_id: int,
    kind: str,
    payload: dict,
    now: datetime,
    next_attempt_at: datetime | None = None,
) -> PushOutboxMessage:
    row = PushOutboxMessage(
        account_id=account_id,
        kind=kind,
        payload=payload,
        next_attempt_at=next_attempt_at or now,
        created_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def lock_due(
    session: AsyncSession, now: datetime, limit: int = 50
) -> list[PushOutboxMessage]:
    """SELECT ... FOR UPDATE SKIP LOCKED over pending rows whose backoff has
    elapsed -- mirrors messaging_outbox_repo.lock_ready. The next_attempt_at
    filter is load-bearing: without it a transient send failure resends every
    dispatcher tick forever."""
    stmt = (
        select(PushOutboxMessage)
        .where(
            PushOutboxMessage.status == "pending",
            PushOutboxMessage.next_attempt_at <= now,
        )
        .order_by(PushOutboxMessage.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
