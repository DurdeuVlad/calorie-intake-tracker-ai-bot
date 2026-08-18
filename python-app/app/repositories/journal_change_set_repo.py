from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.journal_changes import JournalChangeSet
from app.db.models.users import FoodUser


async def find_first_undoable(session: AsyncSession, user: FoodUser, now: datetime) -> JournalChangeSet | None:
    stmt = (
        select(JournalChangeSet)
        .where(JournalChangeSet.user_id == user.id, JournalChangeSet.undone_at.is_(None), JournalChangeSet.expires_at > now)
        # Eager-load mutations: under async SQLAlchemy, accessing a lazy
        # relationship outside an awaited call raises MissingGreenlet, and
        # _undo_last() needs the full mutation list right after this query.
        .options(selectinload(JournalChangeSet.mutations))
        .order_by(JournalChangeSet.created_at.desc(), JournalChangeSet.id.desc())
        .limit(1)
        .with_for_update()
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def delete_expired(session: AsyncSession, before: datetime) -> None:
    await session.execute(delete(JournalChangeSet).where(JournalChangeSet.expires_at < before))
