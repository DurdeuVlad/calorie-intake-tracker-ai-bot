"""Device registry endpoints: register/upsert/re-enable/disable, all scoped
to the caller's account."""

import uuid
from datetime import datetime, timezone

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import get_settings
from app.db.base import session_scope
from app.db.models.devices import MobileDevice
from app.main import create_app
from app.mobile.rate_limit import limiter


@pytest.fixture(autouse=True)
def _isolate_rate_limiter(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mobile_auth_rate_limit_per_minute", 10_000)
    monkeypatch.setattr(settings, "mobile_message_rate_limit_per_minute", 10_000)
    limiter.reset()
    yield
    limiter.reset()


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as c:
        yield c


async def _signup(client) -> dict[str, str]:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct horse battery", "device_id": "dev-1"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _device_body(**overrides) -> dict:
    body = {
        "platform": "ios",
        "push_token": f"apns-{uuid.uuid4().hex}",
        "app_version": "1.2.3",
        "locale": "en-US",
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_register_creates_device(client):
    headers = await _signup(client)
    resp = await client.post("/api/v1/devices", json=_device_body(), headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["platform"] == "ios"
    assert body["app_version"] == "1.2.3"
    assert body["locale"] == "en-US"
    assert body["disabled_at"] is None

    async with session_scope() as session:
        row = (await session.execute(select(MobileDevice))).scalar_one()
        assert row.id == body["id"]
        assert row.push_token is not None
        assert row.last_seen_at is not None


@pytest.mark.asyncio
async def test_register_same_token_upserts_instead_of_duplicating(client):
    headers = await _signup(client)
    token = f"fcm-{uuid.uuid4().hex}"

    first = await client.post(
        "/api/v1/devices", json=_device_body(platform="android", push_token=token), headers=headers
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/v1/devices",
        json=_device_body(platform="ios", push_token=token, app_version="2.0.0"),
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    async with session_scope() as session:
        rows = (await session.execute(select(MobileDevice))).scalars().all()
        assert len(rows) == 1
        assert rows[0].platform == "ios"
        assert rows[0].app_version == "2.0.0"


@pytest.mark.asyncio
async def test_register_reenables_a_disabled_device(client):
    headers = await _signup(client)
    token = f"apns-{uuid.uuid4().hex}"

    created = await client.post(
        "/api/v1/devices", json=_device_body(push_token=token), headers=headers
    )
    device_id = created.json()["id"]

    deleted = await client.delete(f"/api/v1/devices/{device_id}", headers=headers)
    assert deleted.status_code == 204
    async with session_scope() as session:
        row = (await session.execute(select(MobileDevice))).scalar_one()
        assert row.disabled_at is not None

    re_register = await client.post(
        "/api/v1/devices", json=_device_body(push_token=token), headers=headers
    )
    assert re_register.status_code == 200
    assert re_register.json()["id"] == device_id
    assert re_register.json()["disabled_at"] is None

    async with session_scope() as session:
        rows = (await session.execute(select(MobileDevice))).scalars().all()
        assert len(rows) == 1
        assert rows[0].disabled_at is None


@pytest.mark.asyncio
async def test_delete_is_scoped_to_the_callers_account(client):
    headers_a = await _signup(client)
    headers_b = await _signup(client)

    created = await client.post("/api/v1/devices", json=_device_body(), headers=headers_a)
    device_id = created.json()["id"]

    # Another account's device id is indistinguishable from a missing one.
    stolen = await client.delete(f"/api/v1/devices/{device_id}", headers=headers_b)
    assert stolen.status_code == 404

    async with session_scope() as session:
        row = (await session.execute(select(MobileDevice))).scalar_one()
        assert row.disabled_at is None

    own = await client.delete(f"/api/v1/devices/{device_id}", headers=headers_a)
    assert own.status_code == 204
    async with session_scope() as session:
        row = (await session.execute(select(MobileDevice))).scalar_one()
        assert row.disabled_at is not None
        assert row.disabled_at <= datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_list_returns_only_the_callers_devices(client):
    headers_a = await _signup(client)
    headers_b = await _signup(client)

    await client.post("/api/v1/devices", json=_device_body(), headers=headers_a)
    await client.post("/api/v1/devices", json=_device_body(), headers=headers_a)
    await client.post("/api/v1/devices", json=_device_body(), headers=headers_b)

    resp = await client.get("/api/v1/devices", headers=headers_a)
    assert resp.status_code == 200
    assert len(resp.json()["devices"]) == 2

    resp = await client.get("/api/v1/devices", headers=headers_b)
    assert len(resp.json()["devices"]) == 1


@pytest.mark.asyncio
async def test_devices_endpoints_require_auth(client):
    resp = await client.post("/api/v1/devices", json=_device_body())
    assert resp.status_code == 401
    resp = await client.get("/api/v1/devices")
    assert resp.status_code == 401
    resp = await client.delete("/api/v1/devices/1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_rejects_unknown_platform(client):
    headers = await _signup(client)
    resp = await client.post(
        "/api/v1/devices", json=_device_body(platform="windows"), headers=headers
    )
    assert resp.status_code == 422
