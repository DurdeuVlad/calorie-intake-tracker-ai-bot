from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import PrivateFood
from app.db.models.users import FoodUser


async def find_by_user_and_name_ignore_case(session: AsyncSession, user: FoodUser, name: str) -> PrivateFood | None:
    stmt = select(PrivateFood).where(PrivateFood.user_id == user.id, func.lower(PrivateFood.name) == name.lower())
    return (await session.execute(stmt)).scalar_one_or_none()
