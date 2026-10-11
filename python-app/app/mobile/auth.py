"""Mobile API v1 auth surface: signup, login, rotating refresh, and a minimal
/me that proves the get_current_account dependency end-to-end."""

from fastapi import APIRouter, Depends, HTTPException

from app.db.base import session_scope
from app.mobile import service
from app.mobile.dependencies import MobilePrincipal, get_current_account
from app.mobile.rate_limit import auth_rate_limit
from app.mobile.schemas import LoginRequest, MeResponse, RefreshRequest, SignupRequest, TokenResponse

router = APIRouter(prefix="/api/v1/auth", tags=["mobile-auth"])

_rate_limited = [Depends(auth_rate_limit)]


def _to_response(bundle: service.TokenBundle) -> TokenResponse:
    return TokenResponse(
        access_token=bundle.access_token,
        expires_in=bundle.expires_in,
        refresh_token=bundle.refresh_token,
    )


@router.post("/signup", response_model=TokenResponse, status_code=201, dependencies=_rate_limited)
async def signup(body: SignupRequest) -> TokenResponse:
    async with session_scope() as session:
        try:
            bundle = await service.signup(session, body.email, body.password, body.device_id)
        except service.EmailAlreadyRegistered:
            raise HTTPException(status_code=409, detail="email already registered") from None
        return _to_response(bundle)


@router.post("/login", response_model=TokenResponse, dependencies=_rate_limited)
async def login(body: LoginRequest) -> TokenResponse:
    async with session_scope() as session:
        try:
            bundle = await service.login(session, body.email, body.password, body.device_id)
        except service.AuthError:
            raise HTTPException(status_code=401, detail="invalid email or password") from None
        return _to_response(bundle)


@router.post("/refresh", response_model=TokenResponse, dependencies=_rate_limited)
async def refresh(body: RefreshRequest) -> TokenResponse:
    async with session_scope() as session:
        try:
            bundle = await service.refresh(session, body.refresh_token, body.device_id)
        except service.AuthError:
            raise HTTPException(status_code=401, detail="invalid refresh token") from None
        return _to_response(bundle)


@router.get("/me", response_model=MeResponse)
async def me(principal: MobilePrincipal = Depends(get_current_account)) -> MeResponse:
    return MeResponse(
        account_id=principal.account.id,
        email=principal.account.email,
        food_user_id=principal.user.id,
    )
