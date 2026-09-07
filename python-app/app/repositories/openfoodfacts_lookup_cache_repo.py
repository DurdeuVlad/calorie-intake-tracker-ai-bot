from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import OpenFoodFactsLookupCache


async def find(session: AsyncSession, cache_key: str) -> OpenFoodFactsLookupCache | None:
    return (await session.execute(select(OpenFoodFactsLookupCache).where(OpenFoodFactsLookupCache.cache_key == cache_key))).scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    cache_key: str,
    lookup_kind: str,
    status: str,
    payload: str | None,
    fetched_at: datetime,
    expires_at: datetime,
) -> bool:
    insert = pg_insert(OpenFoodFactsLookupCache).values(
        cache_key=cache_key,
        lookup_kind=lookup_kind,
        status=status,
        payload=payload,
        fetched_at=fetched_at,
        expires_at=expires_at,
    )
    update = {
        "lookup_kind": lookup_kind,
        "status": status,
        "payload": payload,
        "fetched_at": fetched_at,
        "expires_at": expires_at,
    }
    if status == "SUCCESS":
        stmt = insert.on_conflict_do_update(
            index_elements=[OpenFoodFactsLookupCache.cache_key],
            set_=update,
        )
    else:
        stmt = insert.on_conflict_do_update(
            index_elements=[OpenFoodFactsLookupCache.cache_key],
            set_=update,
            where=OpenFoodFactsLookupCache.status != "SUCCESS",
        )
    result = await session.execute(stmt)
    return result.rowcount != 0
