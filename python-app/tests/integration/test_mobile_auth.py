import uuid
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import get_settings
from app.db.base import session_scope
from app.db.models.auth import AuthAccount, MobileRefreshToken
from app.main import create_app
from app.messaging.inbound_message import InboundMessage
from app.messaging import inbox_worker
from app.mobile import security
from app.mobile.rate_limit import limiter
from app.repositories import messaging_identity_repo


@pytest.fixture(autouse=True)
def _isolate_rate_limiter(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mobile_auth_rate_limit_per_minute", 10_000)
    limiter.reset()
    yield
    limiter.reset()


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as c:
        yield c


def _email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


async def _signup(client, email: str, password: str = "correct horse battery", device_id: str = "dev-1") -> httpx.Response:
    return await client.post(
        "/api/v1/auth/signup", json={"email": email, "password": password, "device_id": device_id}
    )


@pytest.mark.asyncio
async def test_signup_creates_account_food_user_and_mobile_identity(client):
    email = f"Mixed.Case-{uuid.uuid4().hex[:8]}@Example.COM"
    resp = await _signup(client, email)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["expires_in"] > 0

    async with session_scope() as session:
        account = (await session.execute(select(AuthAccount))).scalar_one()
        # Stored normalized lowercase; password stored only as an argon2 hash.
        assert account.email == email.strip().lower()
        assert account.password_hash is not None and account.password_hash != "correct horse battery"
        # The mobile identity row plugs into the existing resolution path:
        # (provider, external_user_id) -> food_users.
        identity = await messaging_identity_repo.find_by_provider_and_external_id(
            session, "mobile", str(account.id)
        )
        assert identity is not None
        assert identity.user_id == account.food_user_id


@pytest.mark.asyncio
async def test_signup_duplicate_email_conflicts(client):
    email = _email()
    assert (await _signup(client, email)).status_code == 201
    resp = await _signup(client, email.upper())
    assert resp.status_code == 409

    async with session_scope() as session:
        accounts = (await session.execute(select(AuthAccount))).scalars().all()
        assert len(accounts) == 1


@pytest.mark.asyncio
async def test_login_returns_tokens_and_me_resolves_the_food_user(client):
    email = _email()
    password = "correct horse battery"
    await _signup(client, email, password)

    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password, "device_id": "dev-9"}
    )
    assert resp.status_code == 200, resp.text
    tokens = resp.json()

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200, me.text
    payload = me.json()

    async with session_scope() as session:
        account = (await session.execute(select(AuthAccount))).scalar_one()
        assert payload["account_id"] == account.id
        assert payload["email"] == account.email
        # The principal's FoodUser is exactly what the mobile identity row scopes to.
        assert payload["food_user_id"] == account.food_user_id


@pytest.mark.asyncio
async def test_login_wrong_password_is_rejected(client):
    email = _email()
    await _signup(client, email)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong-password", "device_id": "dev-1"}
    )
    assert resp.status_code == 401
    resp = await client.post(
        "/api/v1/auth/login", json={"email": _email(), "password": "wrong-password", "device_id": "dev-1"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_and_reusing_a_rotated_token_revokes_the_chain(client):
    email = _email()
    password = "correct horse battery"
    await _signup(client, email, password)
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password, "device_id": "dev-1"}
    )
    original = login.json()["refresh_token"]

    rotated = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original, "device_id": "dev-1"}
    )
    assert rotated.status_code == 200, rotated.text
    rotated_token = rotated.json()["refresh_token"]
    assert rotated_token != original

    # Reuse of the rotated-out token = theft signal: 401 and the forward chain dies.
    reuse = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original, "device_id": "dev-1"}
    )
    assert reuse.status_code == 401

    successor = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": rotated_token, "device_id": "dev-1"}
    )
    assert successor.status_code == 401

    async with session_scope() as session:
        rows = (
            (await session.execute(select(MobileRefreshToken).order_by(MobileRefreshToken.id)))
            .scalars()
            .all()
        )
        # The theft signal kills the reused token's forward chain (login token
        # -> its rotation). The signup token is a separate chain and must NOT
        # be revoked -- reuse detection scopes to the compromised family only.
        assert len(rows) == 3
        assert rows[0].revoked_at is None
        assert all(r.revoked_at is not None for r in rows[1:])


@pytest.mark.asyncio
async def test_refresh_is_bound_to_the_device_id(client):
    email = _email()
    password = "correct horse battery"
    await _signup(client, email, password)
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password, "device_id": "dev-1"}
    )
    refresh_token = login.json()["refresh_token"]

    wrong_device = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token, "device_id": "dev-2"}
    )
    assert wrong_device.status_code == 401

    # The token itself is still usable from the right device (not revoked by the mismatch).
    ok = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token, "device_id": "dev-1"}
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_expired_access_token_is_rejected(client):
    email = _email()
    resp = await _signup(client, email)
    tokens = resp.json()
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    account_id = me.json()["account_id"]

    expired, _ = security.create_access_token(account_id, ttl=timedelta(seconds=-10))
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mobile_identity_resolves_through_the_existing_inbox_path(client):
    """The signup-created messaging_identities row must resolve to the same
    FoodUser through inbox_worker.resolve_identity_user -- the seam phase 2b's
    mobile messages endpoint will reuse."""
    email = _email()
    await _signup(client, email)

    async with session_scope() as session:
        account = (await session.execute(select(AuthAccount))).scalar_one()
        message = InboundMessage(
            provider="mobile",
            event_id=str(uuid.uuid4()),
            user_id=str(account.id),
            conversation_id="mobile-conv",
            display_name=None,
            language_code="en",
            text="hi",
            caption=None,
        )
        user = await inbox_worker.resolve_identity_user(session, message, "Europe/Bucharest")
        assert user is not None
        assert user.id == account.food_user_id


@pytest.mark.asyncio
async def test_auth_endpoints_are_rate_limited(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mobile_auth_rate_limit_per_minute", 3)
    limiter.reset()

    body = {"email": _email(), "password": "irrelevant-pass", "device_id": "dev-1"}
    codes = []
    for _ in range(4):
        codes.append((await client.post("/api/v1/auth/login", json=body)).status_code)
    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429
