"""/api/v1/link -- the mobile half of cross-surface account linking.

- POST /issue mints the same 8-char, 10-min code the bot's /link command
  produces; the user then types "link CODE" in Telegram to bind that identity
  to this account's FoodUser.
- POST /redeem goes the other way: the bot issued the code, the mobile account
  rebinds its food_user_id onto the code's FoodUser (refused with 409 when the
  current FoodUser already has journal rows).
- GET /status lists which messaging providers share this account's journal.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.db.base import session_scope
from app.mobile.dependencies import MobilePrincipal, get_current_account
from app.mobile.rate_limit import auth_rate_limit, message_rate_limit
from app.mobile.schemas import LinkIssueResponse, LinkRedeemRequest, LinkStatusResponse
from app.repositories import auth_account_repo, frontend_link_code_repo, messaging_identity_repo
from app.services import message_link_service

router = APIRouter(prefix="/api/v1/link", tags=["mobile-link"])

# redeem is a code-guessing surface, so it shares the auth endpoints' stricter
# limiter; status is ordinary account data and uses the message limiter.
_code_limited = [Depends(auth_rate_limit)]


@router.post("/issue", response_model=LinkIssueResponse, dependencies=_code_limited)
async def issue_code(principal: MobilePrincipal = Depends(get_current_account)) -> LinkIssueResponse:
    async with session_scope() as session:
        code = await message_link_service.issue(session, principal.user)
        link = await frontend_link_code_repo.find_by_code(session, code)
        await session.commit()
        return LinkIssueResponse(code=code, expiresAt=link.expires_at)


@router.post("/redeem", response_model=LinkStatusResponse, dependencies=_code_limited)
async def redeem_code(
    body: LinkRedeemRequest,
    principal: MobilePrincipal = Depends(get_current_account),
) -> LinkStatusResponse:
    async with session_scope() as session:
        account = await auth_account_repo.find_by_id(session, principal.account.id)
        if account is None:
            raise HTTPException(status_code=401, detail="invalid or expired access token")
        try:
            await message_link_service.redeem_for_account(session, body.code, account)
        except message_link_service.LinkError:
            raise HTTPException(status_code=400, detail="invalid or expired link code") from None
        except message_link_service.AccountLinkConflict:
            raise HTTPException(
                status_code=409, detail="this account already has journal data and cannot be linked"
            ) from None
        await session.commit()
        providers = await messaging_identity_repo.list_providers(session, account.food_user_id)
        return LinkStatusResponse(linkedProviders=providers)


@router.get("/status", response_model=LinkStatusResponse, dependencies=[Depends(message_rate_limit)])
async def link_status(principal: MobilePrincipal = Depends(get_current_account)) -> LinkStatusResponse:
    async with session_scope() as session:
        providers = await messaging_identity_repo.list_providers(session, principal.user.id)
        return LinkStatusResponse(linkedProviders=providers)
