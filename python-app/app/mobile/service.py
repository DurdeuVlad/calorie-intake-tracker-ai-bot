"""Mobile auth: signup, login, and rotating refresh tokens.

Signup creates an AuthAccount + FoodUser + a messaging_identities(provider='mobile')
row, so the account plugs into the same identity-resolution path the inbox
worker uses for every other provider -- ownership stays food_user-scoped and
the repositories don't change.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.auth import AuthAccount, MobileRefreshToken
from app.db.models.users import FoodUser, UserSettings
from app.mobile import security
from app.repositories import auth_account_repo, messaging_identity_repo, refresh_token_repo

MOBILE_PROVIDER = "mobile"

_DUMMY_PASSWORD_HASH = security.hash_password("not-a-real-password")


class AuthError(ValueError):
    """Generic auth failure -- mapped to 401 at the router."""


class EmailAlreadyRegistered(ValueError):
    """Mapped to 409 at the router."""


@dataclass
class TokenBundle:
    access_token: str
    expires_in: int
    refresh_token: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def _issue_refresh_token(
    session: AsyncSession, account: AuthAccount, device_id: str
) -> tuple[MobileRefreshToken, str]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    plain = security.generate_refresh_token()
    row = MobileRefreshToken(
        account_id=account.id,
        token_hash=security.hash_refresh_token(plain),
        device_id=device_id,
        expires_at=now + timedelta(days=settings.mobile_auth_refresh_token_ttl_days),
        created_at=now,
    )
    session.add(row)
    await session.flush()
    return row, plain


async def _issue_token_pair(
    session: AsyncSession, account: AuthAccount, device_id: str
) -> tuple[TokenBundle, MobileRefreshToken]:
    row, plain = await _issue_refresh_token(session, account, device_id)
    access_token, expires_in = security.create_access_token(account.id)
    return TokenBundle(access_token=access_token, expires_in=expires_in, refresh_token=plain), row


async def signup(session: AsyncSession, email: str, password: str, device_id: str) -> TokenBundle:
    settings = get_settings()
    normalized = normalize_email(email)
    if await auth_account_repo.find_by_email(session, normalized) is not None:
        raise EmailAlreadyRegistered()
    now = datetime.now(timezone.utc)

    user = FoodUser(telegram_user_id=None, display_name=None, created_at=now)
    session.add(user)
    await session.flush()
    session.add(UserSettings(user_id=user.id, timezone=settings.default_timezone))

    account = AuthAccount(
        email=normalized,
        password_hash=security.hash_password(password),
        food_user_id=user.id,
        created_at=now,
        updated_at=now,
    )
    session.add(account)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise EmailAlreadyRegistered() from None

    await messaging_identity_repo.create(session, user, MOBILE_PROVIDER, str(account.id))
    bundle, _ = await _issue_token_pair(session, account, device_id)
    await session.commit()
    return bundle


async def login(session: AsyncSession, email: str, password: str, device_id: str) -> TokenBundle:
    account = await auth_account_repo.find_by_email(session, normalize_email(email))
    if account is None:
        # Verify against a dummy hash so unknown emails don't return faster than
        # wrong passwords (keeps the timing oracle blunt).
        security.verify_password(_DUMMY_PASSWORD_HASH, password)
        raise AuthError("invalid email or password")
    if not security.verify_password(account.password_hash, password):
        raise AuthError("invalid email or password")
    bundle, _ = await _issue_token_pair(session, account, device_id)
    await session.commit()
    return bundle


async def _revoke_chain(session: AsyncSession, token: MobileRefreshToken, now: datetime) -> None:
    """Revoke this token and every token rotated forward from it. Reuse of a
    rotated-out token is a theft signal, so the whole forward chain dies."""
    current: MobileRefreshToken | None = token
    while current is not None:
        if current.revoked_at is None:
            current.revoked_at = now
        next_id = current.rotated_to_id
        current = await refresh_token_repo.find_by_id(session, next_id) if next_id is not None else None


async def refresh(session: AsyncSession, refresh_token: str, device_id: str) -> TokenBundle:
    now = datetime.now(timezone.utc)
    row = await refresh_token_repo.find_by_token_hash(session, security.hash_refresh_token(refresh_token))
    if row is None:
        raise AuthError("invalid refresh token")
    if row.revoked_at is not None or row.rotated_to_id is not None:
        await _revoke_chain(session, row, now)
        await session.commit()
        raise AuthError("invalid refresh token")
    if row.expires_at <= now or row.device_id != device_id:
        raise AuthError("invalid refresh token")

    account = await auth_account_repo.find_by_id(session, row.account_id)
    if account is None:
        raise AuthError("invalid refresh token")

    bundle, successor = await _issue_token_pair(session, account, device_id)
    row.rotated_to_id = successor.id
    await session.commit()
    return bundle
