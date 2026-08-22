from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models.messaging import TelegramAccessGrant


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_telegram_ids(raw_ids: str) -> set[int]:
    """Parse a comma-separated list without ever accepting arbitrary strings."""
    result: set[int] = set()
    for raw in raw_ids.split(","):
        value = raw.strip()
        if not value:
            continue
        if not value.isdigit() or int(value) <= 0:
            raise ValueError("Telegram user IDs must be positive numeric IDs")
        result.add(int(value))
    return result


async def seed_bootstrap_grants(session: AsyncSession, settings: Settings) -> None:
    """Seed bootstrap admins and migrate the old allowlist exactly once per ID.

    Authorization thereafter is read from telegram_access_grants. Keeping the
    legacy list here, rather than in the authorization predicate, lets an
    existing deployment migrate without locking out its current users.
    """
    now = _now()
    admins = parse_telegram_ids(",".join(settings.admin_telegram_user_id_set))
    legacy = parse_telegram_ids(",".join(settings.allowed_telegram_user_id_set))
    for telegram_user_id in admins:
        stmt = insert(TelegramAccessGrant).values(
            telegram_user_id=telegram_user_id, is_admin=True, active=True,
            granted_by=None, created_at=now, updated_at=now,
        ).on_conflict_do_update(
            index_elements=[TelegramAccessGrant.telegram_user_id],
            set_={"is_admin": True, "active": True, "updated_at": now},
        )
        await session.execute(stmt)
    for telegram_user_id in legacy - admins:
        stmt = insert(TelegramAccessGrant).values(
            telegram_user_id=telegram_user_id, is_admin=False, active=True,
            granted_by=None, created_at=now, updated_at=now,
        ).on_conflict_do_nothing(index_elements=[TelegramAccessGrant.telegram_user_id])
        await session.execute(stmt)


async def find(session: AsyncSession, telegram_user_id: int) -> TelegramAccessGrant | None:
    return (await session.execute(
        select(TelegramAccessGrant).where(TelegramAccessGrant.telegram_user_id == telegram_user_id)
    )).scalar_one_or_none()


async def allowed(session: AsyncSession, telegram_user_id: int) -> bool:
    grant = await find(session, telegram_user_id)
    return grant is not None and grant.active


async def is_admin(session: AsyncSession, telegram_user_id: int) -> bool:
    grant = await find(session, telegram_user_id)
    return grant is not None and grant.active and grant.is_admin


async def grant_user(session: AsyncSession, telegram_user_id: int, granted_by: int) -> TelegramAccessGrant:
    now = _now()
    existing = await find(session, telegram_user_id)
    if existing is None:
        existing = TelegramAccessGrant(
            telegram_user_id=telegram_user_id, is_admin=False, active=True,
            granted_by=granted_by, created_at=now, updated_at=now,
        )
        session.add(existing)
    else:
        existing.active = True
        existing.granted_by = granted_by
        existing.updated_at = now
    await session.flush()
    return existing


async def revoke_user(session: AsyncSession, telegram_user_id: int) -> bool:
    existing = await find(session, telegram_user_id)
    if existing is None or existing.is_admin:
        return False
    existing.active = False
    existing.updated_at = _now()
    await session.flush()
    return True
