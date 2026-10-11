"""Repository for companion_memory -- the durable, user-reviewable fact store
(audit section 4.4). Every query is scoped to a FoodUser; there is deliberately
no unscoped lookup path."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.companion import CompanionMemory
from app.db.models.users import FoodUser


def normalize_text(text: str) -> str:
    """Canonical form used for dedupe: whitespace-collapsed, case-folded."""
    return " ".join(text.split()).casefold()


def _active():
    return CompanionMemory.deleted_at.is_(None)


async def list_active(session: AsyncSession, user: FoodUser) -> list[CompanionMemory]:
    stmt = (
        select(CompanionMemory)
        .where(CompanionMemory.user_id == user.id, _active())
        .order_by(CompanionMemory.created_at, CompanionMemory.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def find_active_by_normalized(
    session: AsyncSession, user: FoodUser, normalized: str
) -> CompanionMemory | None:
    stmt = select(CompanionMemory).where(
        CompanionMemory.user_id == user.id,
        _active(),
        CompanionMemory.normalized_text == normalized,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def find_active_by_id(session: AsyncSession, user: FoodUser, memory_id: int) -> CompanionMemory | None:
    stmt = select(CompanionMemory).where(
        CompanionMemory.id == memory_id,
        CompanionMemory.user_id == user.id,
        _active(),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def find_best_match(session: AsyncSession, user: FoodUser, text: str) -> CompanionMemory | None:
    """forget_memory's free-text resolution: an exact normalized match wins;
    otherwise the most recently updated active row containing the fragment."""
    needle = normalize_text(text)
    if not needle:
        return None
    exact = await find_active_by_normalized(session, user, needle)
    if exact is not None:
        return exact
    stmt = (
        select(CompanionMemory)
        .where(
            CompanionMemory.user_id == user.id,
            _active(),
            CompanionMemory.normalized_text.ilike(f"%{_escape_like(needle)}%", escape="\\"),
        )
        .order_by(CompanionMemory.updated_at.desc(), CompanionMemory.id.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def save(
    session: AsyncSession,
    user: FoodUser,
    kind: str,
    text: str,
    source: str = "agent",
) -> tuple[CompanionMemory, bool]:
    """Insert a memory, or return the existing active row when the same
    normalized text is already known. The partial unique index still guards
    against a concurrent insert, in which case we re-read and report the
    winner."""
    normalized = normalize_text(text)
    existing = await find_active_by_normalized(session, user, normalized)
    if existing is not None:
        return existing, False

    now = datetime.now(timezone.utc)
    row = CompanionMemory(
        user_id=user.id,
        kind=kind,
        text=text,
        normalized_text=normalized,
        source=source,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        winner = await find_active_by_normalized(session, user, normalized)
        if winner is not None:
            return winner, False
        raise
    return row, True
