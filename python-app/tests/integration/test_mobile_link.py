import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import get_settings
from app.db.base import session_scope
from app.db.models.auth import AuthAccount
from app.db.models.entries import FoodEntry
from app.db.models.messaging import FrontendLinkCode
from app.main import create_app
from app.mobile.rate_limit import limiter
from app.repositories import frontend_link_code_repo, messaging_identity_repo
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.services import message_link_service


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


def _email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


async def _signup_token(client, email: str | None = None) -> str:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email or _email(), "password": "correct horse battery", "device_id": "dev-1"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _account() -> AuthAccount:
    async with session_scope() as session:
        return (await session.execute(select(AuthAccount))).scalar_one()


@pytest.mark.asyncio
async def test_issue_returns_a_code_that_the_bot_side_can_redeem(client):
    """Direction 1: mobile issues, Telegram redeems via the existing service."""
    token = await _signup_token(client)

    resp = await client.post("/api/v1/link/issue", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["code"]) == 8
    expires_at = datetime.fromisoformat(body["expiresAt"].replace("Z", "+00:00"))
    assert expires_at > datetime.now(timezone.utc)

    async with session_scope() as session:
        account = (await session.execute(select(AuthAccount))).scalar_one()
        # Exactly what the inbox worker does for "link CODE" from Telegram.
        linked_user = await message_link_service.redeem(
            session, body["code"], "telegram", "501", "conv-501"
        )
        await session.commit()
        assert linked_user.id == account.food_user_id

    status = await client.get("/api/v1/link/status", headers=_auth(token))
    assert status.status_code == 200
    assert status.json()["linkedProviders"] == ["mobile", "telegram"]


@pytest.mark.asyncio
async def test_redeem_rebinds_the_account_onto_the_codes_food_user(client):
    """Direction 2: bot side issues, mobile redeems onto the Telegram FoodUser."""
    token = await _signup_token(client)

    async with session_scope() as session:
        telegram_user = await get_or_create_by_telegram_user_id(session, 501, "Tester", "Europe/Bucharest")
        # A Telegram user who can type /link has already messaged the bot, so
        # the inbox worker has bound their telegram identity to this FoodUser.
        await messaging_identity_repo.create(session, telegram_user, "telegram", "501")
        code = await message_link_service.issue(session, telegram_user)
        await session.commit()

    async with session_scope() as session:
        account = (await session.execute(select(AuthAccount))).scalar_one()
        old_food_user_id = account.food_user_id
    assert old_food_user_id != telegram_user.id

    resp = await client.post("/api/v1/link/redeem", json={"code": code}, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["linkedProviders"] == ["mobile", "telegram"]

    async with session_scope() as session:
        account = (await session.execute(select(AuthAccount))).scalar_one()
        assert account.food_user_id == telegram_user.id
        # The mobile identity follows the rebind instead of dangling on the
        # orphaned signup FoodUser.
        identity = await messaging_identity_repo.find_by_provider_and_external_id(
            session, "mobile", str(account.id)
        )
        assert identity.user_id == telegram_user.id
        # The link code is consumed.
        link = await frontend_link_code_repo.find_by_code(session, code)
        assert link.consumed_at is not None


@pytest.mark.asyncio
async def test_redeem_unknown_code_is_a_mapped_error(client):
    token = await _signup_token(client)
    resp = await client.post("/api/v1/link/redeem", json={"code": "ZZZZZZZZ"}, headers=_auth(token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_redeem_expired_code_is_a_mapped_error(client):
    token = await _signup_token(client)

    async with session_scope() as session:
        account = (await session.execute(select(AuthAccount))).scalar_one()
        session.add(
            FrontendLinkCode(
                code="EXPIRED1",
                user_id=account.food_user_id,
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        await session.commit()

    resp = await client.post("/api/v1/link/redeem", json={"code": "EXPIRED1"}, headers=_auth(token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_redeem_onto_a_food_user_with_journal_data_conflicts(client):
    """A mobile account that already logged entries may not rebind -- the rows
    would be orphaned. The code must also stay unconsumed."""
    token = await _signup_token(client)

    async with session_scope() as session:
        account = (await session.execute(select(AuthAccount))).scalar_one()
        session.add(
            FoodEntry(
                user_id=account.food_user_id,
                original_message="morning coffee",
                eaten_at=datetime.now(timezone.utc),
                calories=50,
                created_at=datetime.now(timezone.utc),
            )
        )
        telegram_user = await get_or_create_by_telegram_user_id(session, 502, "Tester", "Europe/Bucharest")
        code = await message_link_service.issue(session, telegram_user)
        await session.commit()

    resp = await client.post("/api/v1/link/redeem", json={"code": code}, headers=_auth(token))
    assert resp.status_code == 409, resp.text

    async with session_scope() as session:
        account = (await session.execute(select(AuthAccount))).scalar_one()
        assert account.food_user_id != telegram_user.id
        link = await frontend_link_code_repo.find_by_code(session, code)
        assert link.consumed_at is None


@pytest.mark.asyncio
async def test_status_lists_only_this_accounts_providers(client):
    token_a = await _signup_token(client)
    token_b = await _signup_token(client)

    status_a = await client.get("/api/v1/link/status", headers=_auth(token_a))
    assert status_a.status_code == 200
    assert status_a.json()["linkedProviders"] == ["mobile"]

    # A mobile-issued code cannot be redeemed by another mobile account:
    # food_user_id is a 1:1 FK, so two app accounts can never share a journal.
    issue = await client.post("/api/v1/link/issue", headers=_auth(token_a))
    code = issue.json()["code"]
    resp = await client.post("/api/v1/link/redeem", json={"code": code}, headers=_auth(token_b))
    assert resp.status_code == 409

    async with session_scope() as session:
        accounts = (await session.execute(select(AuthAccount).order_by(AuthAccount.id))).scalars().all()
        assert accounts[0].food_user_id != accounts[1].food_user_id
        # A's side is untouched and B's status still shows only its own providers.
        link = await frontend_link_code_repo.find_by_code(session, code)
        assert link.consumed_at is None

    status_b = await client.get("/api/v1/link/status", headers=_auth(token_b))
    assert status_b.json()["linkedProviders"] == ["mobile"]


@pytest.mark.asyncio
async def test_link_endpoints_require_a_valid_token(client):
    assert (await client.post("/api/v1/link/issue")).status_code == 401
    assert (await client.post("/api/v1/link/redeem", json={"code": "ABCDEFGH"})).status_code == 401
    assert (await client.get("/api/v1/link/status")).status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert (await client.post("/api/v1/link/issue", headers=bad)).status_code == 401
    assert (await client.get("/api/v1/link/status", headers=bad)).status_code == 401
