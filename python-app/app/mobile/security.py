"""Password hashing (argon2) and token primitives for the mobile API.

Access tokens are short-lived HS256 JWTs. Refresh tokens are opaque random
strings -- only their SHA-256 hash is stored at rest.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.config import get_settings

ISSUER = "food-journal-mobile"
ALGORITHM = "HS256"

_ph = PasswordHasher()
_ephemeral_secret: str | None = None


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        return False
    try:
        return _ph.verify(password_hash, password)
    except VerificationError:
        return False


def _signing_secret() -> str:
    global _ephemeral_secret
    configured = get_settings().mobile_auth_jwt_secret
    if configured:
        return configured
    if _ephemeral_secret is None:
        _ephemeral_secret = secrets.token_hex(32)
    return _ephemeral_secret


def create_access_token(account_id: int, ttl: timedelta | None = None) -> tuple[str, int]:
    if ttl is None:
        ttl = timedelta(minutes=get_settings().mobile_auth_access_token_ttl_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account_id),
        "iss": ISSUER,
        "iat": now,
        "exp": now + ttl,
        "typ": "access",
    }
    return jwt.encode(payload, _signing_secret(), algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_access_token(token: str) -> int:
    """Return the account id from a valid access token. Raises jwt.PyJWTError
    (incl. ExpiredSignatureError) or ValueError on anything malformed."""
    payload = jwt.decode(token, _signing_secret(), algorithms=[ALGORITHM], issuer=ISSUER)
    if payload.get("typ") != "access":
        raise ValueError("not an access token")
    return int(payload["sub"])


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
