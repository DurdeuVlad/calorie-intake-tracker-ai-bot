from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.conversation import ConversationMemory
from app.db.models.users import FoodUser
from app.repositories import conversation_memory_repo

MAX_CONTENT_LENGTH = 3500


def _truncate(text: str | None) -> str:
    if text is None:
        return ""
    return text if len(text) <= MAX_CONTENT_LENGTH else text[:MAX_CONTENT_LENGTH]


async def recent(session: AsyncSession, user: FoodUser) -> list[ConversationMemory]:
    return await conversation_memory_repo.recent(session, user)


async def record_turn(session: AsyncSession, user: FoodUser, user_message: str, assistant_message: str) -> None:
    """Records exactly one user+assistant pair for a genuine inbound turn. Callers
    MUST NOT invoke this for internal/system-triggered calls (e.g. the identity
    bootstrap that provisions a first-time user) -- a real bug in the Java
    predecessor did exactly that at one call site and double-recorded memory for
    the same logical turn. Keep this called from exactly one place: the inbox
    worker's main message-handling path, right after computing the real reply."""
    now = datetime.now(UTC)
    session.add(ConversationMemory(user_id=user.id, role="user", content=_truncate(user_message), created_at=now))
    session.add(ConversationMemory(user_id=user.id, role="assistant", content=_truncate(assistant_message), created_at=now))
    await session.flush()
    await conversation_memory_repo.prune_beyond_max(session, user)
