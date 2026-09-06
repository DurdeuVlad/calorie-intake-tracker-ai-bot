from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.messaging import FrontendLinkCode


async def find_by_code(session: AsyncSession, code: str, *, for_update: bool = False) -> FrontendLinkCode | None:
    stmt = select(FrontendLinkCode).where(FrontendLinkCode.code == code)
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def exists(session: AsyncSession, code: str) -> bool:
    return await find_by_code(session, code) is not None
