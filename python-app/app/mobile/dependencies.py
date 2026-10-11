"""FastAPI dependency that validates a mobile access token and resolves the
AuthAccount + FoodUser behind it. Later mobile endpoints reuse this."""

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.base import session_scope
from app.db.models.auth import AuthAccount
from app.db.models.users import FoodUser
from app.mobile import security
from app.repositories import auth_account_repo


@dataclass
class MobilePrincipal:
    account: AuthAccount
    user: FoodUser


_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_account(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> MobilePrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        account_id = security.decode_access_token(credentials.credentials)
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized() from None

    async with session_scope() as session:
        account = await auth_account_repo.find_by_id(session, account_id)
        if account is None:
            raise _unauthorized()
        user = await session.get(FoodUser, account.food_user_id)
        if user is None:
            raise _unauthorized()
        return MobilePrincipal(account=account, user=user)
