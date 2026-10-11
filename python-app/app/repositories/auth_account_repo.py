from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import AuthAccount


async def find_by_email(session: AsyncSession, email: str) -> AuthAccount | None:
    stmt = select(AuthAccount).where(AuthAccount.email == email)
    return (await session.execute(stmt)).scalar_one_or_none()


async def find_by_id(session: AsyncSession, account_id: int) -> AuthAccount | None:
    stmt = select(AuthAccount).where(AuthAccount.id == account_id)
    return (await session.execute(stmt)).scalar_one_or_none()
