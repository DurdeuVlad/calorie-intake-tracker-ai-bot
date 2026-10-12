"""Push outbox transport: drain due push_outbox rows through an injected
send function.

No real FCM/APNs credentials exist yet, so the sender is a seam: the default
`log_send_push` stub just logs and reports success. A real provider slots in
later by passing its own async callable with the same signature -- the drain
loop, locking, and retry/backoff policy don't change.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.devices import PushOutboxMessage
from app.repositories import push_outbox_repo

logger = logging.getLogger(__name__)

SendPush = Callable[[PushOutboxMessage], Awaitable[None]]


async def log_send_push(row: PushOutboxMessage) -> None:
    """Stub sender: pretends the push went out. Replaced by the real FCM/APNs
    provider once credentials land."""
    logger.info(
        "push stub send: outbox_id=%s account_id=%s kind=%s payload=%s",
        row.id,
        row.account_id,
        row.kind,
        row.payload,
    )


async def drain_push_outbox(
    session: AsyncSession,
    send_push: SendPush = log_send_push,
    *,
    limit: int = 50,
    now: datetime | None = None,
) -> int:
    """Send up to `limit` due pending rows. Rows are claimed FOR UPDATE SKIP
    LOCKED so concurrent drainers don't double-send; the caller owns the
    transaction and commits. A sender exception leaves the row pending behind
    an exponential backoff until it exhausts PUSH_MAX_ATTEMPTS and is marked
    failed."""
    now = now or datetime.now(timezone.utc)
    rows = await push_outbox_repo.lock_due(session, now, limit=limit)
    for row in rows:
        try:
            await send_push(row)
        except Exception:
            logger.exception("Push send failed: outbox_id=%s", row.id)
            row.record_failure(now)
        else:
            row.mark_sent(now)
    return len(rows)
