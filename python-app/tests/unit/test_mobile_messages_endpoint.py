"""Endpoint-level unit tests for POST /api/v1/messages.

Drives the real router over ASGI with the three DB-bound seams stubbed (auth
principal, session_scope, record_turn) so the request/response contract --
content-type handling, transcription, action capture, error mapping -- is
verified without Postgres. tests/integration/test_mobile_messages.py covers
the same journeys against the real auth + database.
"""

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio

from app.config import get_settings
from app.domain.agent_types import AgentToolResult, ToolCall
from app.main import create_app
from app.mobile import journal_turn, messages
from app.mobile.dependencies import MobilePrincipal, get_current_account
from app.mobile.rate_limit import limiter


@pytest.fixture(autouse=True)
def _isolate_rate_limiter(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mobile_auth_rate_limit_per_minute", 10_000)
    monkeypatch.setattr(settings, "mobile_message_rate_limit_per_minute", 10_000)
    limiter.reset()
    yield
    limiter.reset()


class FakeJournal:
    def __init__(self, reply: str = "noted", actions: list[dict] | None = None, failure: Exception | None = None):
        self.reply = reply
        self.actions = actions or []
        self.failure = failure
        self.calls: list[dict] = []

    async def handle(self, session, user, chat_id, message, trace=None):
        self.calls.append({"chat_id": chat_id, "message": message})
        if self.failure is not None:
            raise self.failure
        if trace is not None and self.actions:
            trace.tool_result(
                ToolCall(id="call-1", name="apply_journal_actions", arguments="{}"),
                AgentToolResult.success({"results": self.actions, "undoAvailable": True}),
            )
        return self.reply


class FakeVoice:
    def __init__(self, transcript: str = "am mancat un mar"):
        self.transcript = transcript
        self.calls: list[tuple[bytes, str | None]] = []

    async def transcribe(self, data: bytes, mime_type: str | None) -> str:
        self.calls.append((data, mime_type))
        return self.transcript


class _FakeSession:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True


@pytest_asyncio.fixture
async def harness(monkeypatch):
    deps = journal_turn.MobileJournalDeps(journal=FakeJournal(), voice=FakeVoice())
    session = _FakeSession()
    recorded: list[tuple[str, str]] = []

    @asynccontextmanager
    async def fake_session_scope():
        yield session

    async def fake_record_turn(db_session, user, user_message, assistant_message):
        recorded.append((user_message, assistant_message))

    monkeypatch.setattr(messages, "session_scope", fake_session_scope)
    monkeypatch.setattr(journal_turn, "record_turn", fake_record_turn)

    app = create_app()
    app.dependency_overrides[journal_turn.get_message_deps] = lambda: deps
    principal = MobilePrincipal(account=SimpleNamespace(id=7), user=SimpleNamespace(id=3))
    app.dependency_overrides[get_current_account] = lambda: principal

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield SimpleNamespace(client=c, deps=deps, session=session, recorded=recorded)


_AUTH = {"Authorization": "Bearer test-token"}


@pytest.mark.asyncio
async def test_text_message_returns_reply_and_records_turn(harness):
    resp = await harness.client.post("/api/v1/messages", json={"text": "2 boiled eggs"}, headers=_AUTH)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"reply": "noted", "actions": []}

    call = harness.deps.journal.calls[-1]
    assert call["message"] == "2 boiled eggs"
    assert call["chat_id"] == "7"  # numeric account id: the executor needs int(chat_id)
    assert harness.session.committed
    assert harness.recorded == [("2 boiled eggs", "noted")]


@pytest.mark.asyncio
async def test_apply_journal_actions_results_shape_confirmation_card(harness):
    harness.deps.journal.actions = [
        {
            "ok": True,
            "type": "CREATE",
            "entry": {"id": 42, "calories": 95, "eatenAt": "2026-10-12T08:30:00+00:00", "description": "un mar"},
            "date": "2026-10-12",
        },
        {"ok": False, "type": "EDIT", "message": "No matching journal entry exists."},
    ]
    resp = await harness.client.post("/api/v1/messages", json={"text": "apple then fix it"}, headers=_AUTH)
    assert resp.status_code == 200, resp.text
    assert resp.json()["actions"] == [
        {
            "ok": True,
            "type": "CREATE",
            "entry": {"id": 42, "calories": 95, "eaten_at": "2026-10-12T08:30:00+00:00", "description": "un mar"},
            "date": "2026-10-12",
            "message": None,
        },
        {"ok": False, "type": "EDIT", "entry": None, "date": None, "message": "No matching journal entry exists."},
    ]


@pytest.mark.asyncio
async def test_audio_message_is_transcribed_then_run(harness):
    resp = await harness.client.post(
        "/api/v1/messages",
        files={"audio": ("note.ogg", b"fake-opus-bytes", "audio/ogg")},
        headers=_AUTH,
    )
    assert resp.status_code == 200, resp.text
    assert harness.deps.voice.calls == [(b"fake-opus-bytes", "audio/ogg")]
    assert harness.deps.journal.calls[-1]["message"] == "am mancat un mar"


@pytest.mark.asyncio
async def test_audio_caption_is_appended_like_telegram(harness):
    resp = await harness.client.post(
        "/api/v1/messages",
        files={"audio": ("note.m4a", b"fake-m4a", "audio/mp4")},
        data={"caption": "that was breakfast"},
        headers=_AUTH,
    )
    assert resp.status_code == 200, resp.text
    assert harness.deps.journal.calls[-1]["message"] == "am mancat un mar\nUser caption: that was breakfast"


@pytest.mark.asyncio
async def test_multipart_without_audio_is_422(harness):
    resp = await harness.client.post(
        "/api/v1/messages",
        files={"note": (None, "no file here")},
        headers=_AUTH,
    )
    assert resp.status_code == 422
    assert harness.deps.voice.calls == []


@pytest.mark.asyncio
async def test_unauthenticated_is_401():
    # No dependency overrides: get_current_account rejects before touching the DB.
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.post("/api/v1/messages", json={"text": "hi"})).status_code == 401
        bad = {"Authorization": f"Bearer {uuid.uuid4().hex}"}
        assert (await c.post("/api/v1/messages", json={"text": "hi"}, headers=bad)).status_code == 401


@pytest.mark.asyncio
async def test_oversize_audio_is_413(harness, monkeypatch):
    monkeypatch.setattr(messages, "MAX_VOICE_BYTES", 4)
    resp = await harness.client.post(
        "/api/v1/messages",
        files={"audio": ("big.ogg", b"way-too-large-payload", "audio/ogg")},
        headers=_AUTH,
    )
    assert resp.status_code == 413
    assert harness.deps.voice.calls == []


@pytest.mark.asyncio
async def test_agent_failure_maps_to_502_without_internals(harness):
    harness.deps.journal.failure = RuntimeError("secret internal detail")
    resp = await harness.client.post("/api/v1/messages", json={"text": "2 eggs"}, headers=_AUTH)
    assert resp.status_code == 502
    assert "secret internal detail" not in resp.text
    assert "RuntimeError" not in resp.text


@pytest.mark.asyncio
async def test_unsupported_content_type_is_415(harness):
    resp = await harness.client.post(
        "/api/v1/messages", content=b"hi", headers={**_AUTH, "Content-Type": "text/plain"}
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_blank_text_is_422(harness):
    resp = await harness.client.post("/api/v1/messages", json={"text": "   "}, headers=_AUTH)
    assert resp.status_code == 422
    assert harness.deps.journal.calls == []
