"""Repository for user-scoped food aliases (issue #108).

Uses a database-level upsert (ON CONFLICT) targeting the case-insensitive
unique constraint on (user_id, alias_lower) so concurrent save_alias calls
for the same alias cannot create duplicate rows. `alias_lower` is a stored
generated column (`lower(alias)`) so the conflict target is a plain column
list, not an expression."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.aliases import FoodAlias
from app.db.models.users import FoodUser


async def find_by_user_and_alias_ignore_case(
    session: AsyncSession, user: FoodUser, alias: str
) -> FoodAlias | None:
    stmt = select(FoodAlias).where(
        FoodAlias.user_id == user.id,
        func.lower(FoodAlias.alias) == alias.lower(),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_by_user(session: AsyncSession, user: FoodUser) -> list[FoodAlias]:
    stmt = (
        select(FoodAlias)
        .where(FoodAlias.user_id == user.id)
        .order_by(FoodAlias.alias.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def upsert(
    session: AsyncSession,
    user: FoodUser,
    alias: str,
    canonical_name: str,
    calories_per_100g: int | None = None,
    fixed_calories: int | None = None,
) -> FoodAlias:
    """Atomic upsert targeting the case-insensitive unique constraint.

    The conflict target is (user_id, alias_lower). alias_lower is a stored
    generated column, so PostgreSQL computes it from the inserted alias and
    uses it for conflict detection."""
    from datetime import UTC, datetime

    stmt = (
        pg_insert(FoodAlias)
        .values(
            user_id=user.id,
            alias=alias,
            canonical_name=canonical_name,
            calories_per_100g=calories_per_100g,
            fixed_calories=fixed_calories,
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_update(
            index_elements=["user_id", "alias_lower"],
            set_={
                "canonical_name": canonical_name,
                "calories_per_100g": calories_per_100g,
                "fixed_calories": fixed_calories,
            },
        )
        .returning(FoodAlias)
    )
    result = await session.execute(stmt)
    return result.scalar_one()
