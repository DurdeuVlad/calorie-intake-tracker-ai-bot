"""Cross-provider account linking, ported from MessageLinkService.java. A
Telegram user runs /link to get an 8-char code (10-min TTL); redeeming it from
Mattermost via "link CODE" attaches that Mattermost identity to the SAME
FoodUser, so both surfaces share one food journal."""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.messaging import FrontendLinkCode
from app.db.models.users import FoodUser
from app.repositories import frontend_link_code_repo, messaging_identity_repo

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # excludes ambiguous chars (I, O, 0, 1)
_CODE_LENGTH = 8
_TTL = timedelta(minutes=10)


class LinkError(ValueError):
    pass


async def issue(session: AsyncSession, user: FoodUser) -> str:
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))
        if not await frontend_link_code_repo.exists(session, code):
            break
    session.add(FrontendLinkCode(code=code, user_id=user.id, expires_at=datetime.now(timezone.utc) + _TTL))
    await session.flush()
    return code


async def redeem(session: AsyncSession, code: str, provider: str, external_user_id: str, conversation_id: str) -> FoodUser:
    now = datetime.now(timezone.utc)
    link = await frontend_link_code_repo.find_by_code(session, code)
    if link is None or not link.redeemable(now):
        raise LinkError("invalid or expired link code")
    if await messaging_identity_repo.find_by_provider_and_external_id(session, provider, external_user_id) is not None:
        raise LinkError("messaging account is already linked")

    from sqlalchemy import select

    user = (await session.execute(select(FoodUser).where(FoodUser.id == link.user_id))).scalar_one()
    identity = await messaging_identity_repo.create(session, user, provider, external_user_id)
    await messaging_identity_repo.ensure_route(session, user, provider, conversation_id)
    link.consume(now)
    return user
