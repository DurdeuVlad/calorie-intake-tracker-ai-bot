from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.messaging import MessagingIdentity, MessagingRoute
from app.db.models.users import FoodUser


async def find_by_provider_and_external_id(
    session: AsyncSession, provider: str, external_user_id: str
) -> MessagingIdentity | None:
    stmt = select(MessagingIdentity).where(
        MessagingIdentity.provider == provider, MessagingIdentity.external_user_id == external_user_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create(session: AsyncSession, user: FoodUser, provider: str, external_user_id: str) -> MessagingIdentity:
    identity = MessagingIdentity(user_id=user.id, provider=provider, external_user_id=external_user_id)
    session.add(identity)
    await session.flush()
    return identity


async def ensure_route(session: AsyncSession, user: FoodUser, provider: str, conversation_id: str) -> MessagingRoute:
    stmt = select(MessagingRoute).where(
        MessagingRoute.user_id == user.id, MessagingRoute.provider == provider, MessagingRoute.conversation_id == conversation_id
    )
    route = (await session.execute(stmt)).scalar_one_or_none()
    if route is not None:
        return route
    route = MessagingRoute(user_id=user.id, provider=provider, conversation_id=conversation_id)
    session.add(route)
    await session.flush()
    return route
