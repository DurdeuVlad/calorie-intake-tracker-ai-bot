"""/api/v1/devices -- push token registry for the mobile app.

POST registers or refreshes a device: the (account_id, push_token) pair is
unique, so token refreshes and re-installs upsert onto the same row -- mutable
fields update, last_seen_at bumps, and a previously disabled row re-enables.
DELETE disables (soft) so the token stops receiving pushes; rows are scoped to
the caller's account so another user's device id just looks like a 404.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.db.base import session_scope
from app.db.models.devices import MobileDevice
from app.mobile.dependencies import MobilePrincipal, get_current_account
from app.mobile.rate_limit import message_rate_limit
from app.mobile.schemas import DeviceListResponse, DeviceRegisterRequest, DeviceResponse
from app.repositories import mobile_device_repo

router = APIRouter(prefix="/api/v1/devices", tags=["mobile-devices"])

_rate_limited = [Depends(message_rate_limit)]


def _to_response(row: MobileDevice) -> DeviceResponse:
    return DeviceResponse(
        id=row.id,
        platform=row.platform,
        app_version=row.app_version,
        locale=row.locale,
        created_at=row.created_at,
        last_seen_at=row.last_seen_at,
        disabled_at=row.disabled_at,
    )


@router.post("", response_model=DeviceResponse, dependencies=_rate_limited)
async def register_device(
    body: DeviceRegisterRequest,
    principal: MobilePrincipal = Depends(get_current_account),
) -> DeviceResponse:
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        row = await mobile_device_repo.find_by_account_and_token(
            session, principal.account.id, body.push_token
        )
        if row is None:
            row = MobileDevice(
                account_id=principal.account.id,
                platform=body.platform,
                push_token=body.push_token,
                app_version=body.app_version,
                locale=body.locale,
                created_at=now,
                updated_at=now,
                last_seen_at=now,
            )
            session.add(row)
        else:
            row.refresh(body.platform, body.app_version, body.locale, now)
        await session.commit()
        return _to_response(row)


@router.get("", response_model=DeviceListResponse, dependencies=_rate_limited)
async def list_devices(
    principal: MobilePrincipal = Depends(get_current_account),
) -> DeviceListResponse:
    async with session_scope() as session:
        rows = await mobile_device_repo.list_for_account(session, principal.account.id)
        return DeviceListResponse(devices=[_to_response(row) for row in rows])


@router.delete("/{device_id}", status_code=204, dependencies=_rate_limited)
async def disable_device(
    device_id: int,
    principal: MobilePrincipal = Depends(get_current_account),
) -> None:
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        row = await mobile_device_repo.find_by_id_for_account(
            session, principal.account.id, device_id
        )
        if row is None:
            raise HTTPException(status_code=404, detail="device not found")
        row.disable(now)
        await session.commit()
