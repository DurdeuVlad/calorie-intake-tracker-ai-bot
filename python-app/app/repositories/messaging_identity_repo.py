from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    stmt = (
        pg_insert(MessagingIdentity)
        .values(user_id=user.id, provider=provider, external_user_id=external_user_id)
        .on_conflict_do_nothing(index_elements=["provider", "external_user_id"])
        .returning(MessagingIdentity.id)
    )
    identity_id = (await session.execute(stmt)).scalar_one_or_none()
    if identity_id is None:
        identity = await find_by_provider_and_external_id(session, provider, external_user_id)
        if identity is None:
            raise RuntimeError("Messaging identity was not available after conflict")
        return identity
    return await session.get(MessagingIdentity, identity_id)


async def ensure_route(session: AsyncSession, user: FoodUser, provider: str, conversation_id: str) -> MessagingRoute:
    stmt = (
        pg_insert(MessagingRoute)
        .values(user_id=user.id, provider=provider, conversation_id=conversation_id)
        .on_conflict_do_nothing(index_elements=["user_id", "provider", "conversation_id"])
        .returning(MessagingRoute.id)
    )
    route_id = (await session.execute(stmt)).scalar_one_or_none()
    if route_id is None:
        route_stmt = select(MessagingRoute).where(
            MessagingRoute.user_id == user.id,
            MessagingRoute.provider == provider,
            MessagingRoute.conversation_id == conversation_id,
        )
        route = (await session.execute(route_stmt)).scalar_one_or_none()
        if route is None:
            raise RuntimeError("Messaging route was not available after conflict")
        return route
    return await session.get(MessagingRoute, route_id)
