import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.messaging import MessagingOutboundMessage


# This process-local notification complements (never replaces) the durable
# outbox table.  A restart or a missed notification simply falls back to the
# dispatcher's periodic database check.
_dispatch_requested = asyncio.Event()


def request_dispatch() -> None:
    """Wake the local dispatcher after the caller has committed an outbox row."""
    _dispatch_requested.set()


async def wait_for_dispatch(timeout_seconds: float) -> None:
    try:
        await asyncio.wait_for(_dispatch_requested.wait(), timeout=timeout_seconds)
    except TimeoutError:
        pass


def begin_dispatch_cycle() -> None:
    """Consume a prior wake before checking the durable queue."""
    _dispatch_requested.clear()


async def reply(session: AsyncSession, provider: str, conversation_id: str, text: str) -> None:
    session.add(
        MessagingOutboundMessage(
            provider=provider,
            conversation_id=conversation_id,
            text=text,
            next_attempt_at=datetime.now(timezone.utc),
        )
    )


def fit(text: str | None, limit: int) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    suffix = "\n[Message truncated]"
    if limit <= len(suffix):
        return suffix[:limit]
    return text[: limit - len(suffix)] + suffix
