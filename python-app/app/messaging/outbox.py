from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.messaging import MessagingOutboundMessage


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
