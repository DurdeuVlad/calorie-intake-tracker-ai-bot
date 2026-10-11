from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import MobileRefreshToken


async def find_by_token_hash(session: AsyncSession, token_hash: str) -> MobileRefreshToken | None:
    stmt = select(MobileRefreshToken).where(MobileRefreshToken.token_hash == token_hash)
    return (await session.execute(stmt)).scalar_one_or_none()


async def find_by_id(session: AsyncSession, token_id: int) -> MobileRefreshToken | None:
    stmt = select(MobileRefreshToken).where(MobileRefreshToken.id == token_id)
    return (await session.execute(stmt)).scalar_one_or_none()
