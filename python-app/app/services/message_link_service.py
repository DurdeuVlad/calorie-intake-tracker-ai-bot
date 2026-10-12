"""Cross-provider account linking, ported from MessageLinkService.java. A
Telegram user runs /link to get an 8-char code (10-min TTL); redeeming it from
Mattermost via "link CODE" attaches that Mattermost identity to the SAME
FoodUser, so both surfaces share one food journal.

The mobile side reuses the same code: a mobile account can't attach a new
messaging identity (the code carries no provider), so redeem_for_account
instead rebinds the account's 1:1 auth_accounts.food_user_id to the code's
FoodUser -- refused when the current FoodUser already has journal rows,
because rebinding would orphan real history.
"""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import AuthAccount
from app.db.models.entries import FoodEntry
from app.db.models.journal_changes import JournalChangeSet
from app.db.models.messaging import FrontendLinkCode
from app.db.models.users import FoodUser
from app.mobile.service import MOBILE_PROVIDER
from app.repositories import frontend_link_code_repo, messaging_identity_repo

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # excludes ambiguous chars (I, O, 0, 1)
_CODE_LENGTH = 8
_TTL = timedelta(minutes=10)


class LinkError(ValueError):
    pass


class AccountLinkConflict(ValueError):
    """Mapped to 409 at the router: the account's current FoodUser is not the
    empty one signup created, so rebinding is unsafe."""


async def issue(session: AsyncSession, user: FoodUser) -> str:
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))
        if not await frontend_link_code_repo.exists(session, code):
            break
    session.add(FrontendLinkCode(code=code, user_id=user.id, expires_at=datetime.now(timezone.utc) + _TTL))
    await session.flush()
    return code


async def _require_redeemable(session: AsyncSession, code: str, now: datetime) -> FrontendLinkCode:
    link = await frontend_link_code_repo.find_by_code(session, code)
    if link is None or not link.redeemable(now):
        raise LinkError("invalid or expired link code")
    return link


async def redeem(session: AsyncSession, code: str, provider: str, external_user_id: str, conversation_id: str) -> FoodUser:
    now = datetime.now(timezone.utc)
    link = await _require_redeemable(session, code, now)
    if await messaging_identity_repo.find_by_provider_and_external_id(session, provider, external_user_id) is not None:
        raise LinkError("messaging account is already linked")

    user = (await session.execute(select(FoodUser).where(FoodUser.id == link.user_id))).scalar_one()
    identity = await messaging_identity_repo.create(session, user, provider, external_user_id)
    await messaging_identity_repo.ensure_route(session, user, provider, conversation_id)
    link.consume(now)
    return user


async def _has_journal_data(session: AsyncSession, user_id: int) -> bool:
    entry = await session.execute(select(FoodEntry.id).where(FoodEntry.user_id == user_id).limit(1))
    if entry.first() is not None:
        return True
    change_set = await session.execute(
        select(JournalChangeSet.id).where(JournalChangeSet.user_id == user_id).limit(1)
    )
    return change_set.first() is not None


async def redeem_for_account(session: AsyncSession, code: str, account: AuthAccount) -> FoodUser:
    """Mobile-side redeem. Same code validation/consume semantics as redeem(),
    minus the messaging-identity binding -- instead the account's food_user_id
    is re-pointed at the code's FoodUser (conflict when that FoodUser already
    belongs to a different AuthAccount -- food_user_id is 1:1 -- or when the
    account's own FoodUser has journal data). The account's existing provider=
    'mobile' identity follows the rebind so identity resolution and /link/status
    keep reflecting which providers share this journal. The code's FoodUser
    (e.g. the Telegram user's history) is never modified or merged."""
    now = datetime.now(timezone.utc)
    link = await _require_redeemable(session, code, now)
    if link.user_id != account.food_user_id:
        owner_id = (
            await session.execute(
                select(AuthAccount.id).where(AuthAccount.food_user_id == link.user_id)
            )
        ).scalar_one_or_none()
        # food_user_id is a 1:1 FK -- a mobile-issued code can only be consumed
        # by a messaging identity, never by a second mobile account.
        if owner_id is not None and owner_id != account.id:
            raise AccountLinkConflict("food user is already bound to another account")
        if await _has_journal_data(session, account.food_user_id):
            raise AccountLinkConflict("mobile account already has journal data")
        account.food_user_id = link.user_id
        identity = await messaging_identity_repo.find_by_provider_and_external_id(
            session, MOBILE_PROVIDER, str(account.id)
        )
        if identity is not None:
            identity.user_id = link.user_id
    link.consume(now)
    return (await session.execute(select(FoodUser).where(FoodUser.id == link.user_id))).scalar_one()
