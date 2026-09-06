from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.users import FoodUser, UserSettings


async def find_by_telegram_user_id(session: AsyncSession, telegram_user_id: int) -> FoodUser | None:
    stmt = select(FoodUser).where(FoodUser.telegram_user_id == telegram_user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_or_create_by_telegram_user_id(
    session: AsyncSession, telegram_user_id: int, display_name: str | None, default_timezone: str
) -> FoodUser:
    user = await find_by_telegram_user_id(session, telegram_user_id)
    if user is not None:
        return user

    try:
        async with session.begin_nested():
            user = FoodUser(telegram_user_id=telegram_user_id, display_name=display_name, created_at=datetime.now(UTC))
            session.add(user)
            await session.flush()
            session.add(UserSettings(user_id=user.id, timezone=default_timezone))
            await session.flush()
    except IntegrityError:
        user = await find_by_telegram_user_id(session, telegram_user_id)
        if user is None:
            raise
    return user


async def lock_for_journal_mutation(session: AsyncSession, user_id: int) -> None:
    stmt = select(FoodUser.id).where(FoodUser.id == user_id).with_for_update()
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise ValueError("FoodUser missing for journal mutation")


async def get_settings(session: AsyncSession, user_id: int) -> UserSettings:
    stmt = select(UserSettings).where(UserSettings.user_id == user_id)
    settings = (await session.execute(stmt)).scalar_one_or_none()
    if settings is None:
        raise ValueError(f"UserSettings missing for user_id={user_id}")
    return settings
