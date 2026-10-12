from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.devices import MobileDevice


async def find_by_account_and_token(
    session: AsyncSession, account_id: int, push_token: str
) -> MobileDevice | None:
    stmt = select(MobileDevice).where(
        MobileDevice.account_id == account_id,
        MobileDevice.push_token == push_token,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def find_by_id_for_account(
    session: AsyncSession, account_id: int, device_id: int
) -> MobileDevice | None:
    """Device lookup scoped to the owning account -- a row owned by somebody
    else is indistinguishable from a missing one (404 either way)."""
    stmt = select(MobileDevice).where(
        MobileDevice.id == device_id,
        MobileDevice.account_id == account_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_for_account(session: AsyncSession, account_id: int) -> list[MobileDevice]:
    stmt = (
        select(MobileDevice)
        .where(MobileDevice.account_id == account_id)
        .order_by(MobileDevice.id)
    )
    return list((await session.execute(stmt)).scalars().all())
