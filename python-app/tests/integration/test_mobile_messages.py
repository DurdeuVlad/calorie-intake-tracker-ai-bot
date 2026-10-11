import uuid

import httpx
import pytest
import pytest_asyncio

from app.config import get_settings
from app.domain.agent_types import AgentToolResult, ToolCall
from app.main import create_app
from app.mobile import journal_turn, messages
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
    """Stands in for JournalApplicationService. Records the message/chat_id it
    was invoked with and optionally emits an apply_journal_actions tool result
    through the per-run trace sink, like the real agent loop does."""

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


@pytest_asyncio.fixture
async def deps():
    return journal_turn.MobileJournalDeps(journal=FakeJournal(), voice=FakeVoice())


@pytest_asyncio.fixture
async def client(deps):
    app = create_app()
    app.dependency_overrides[journal_turn.get_message_deps] = lambda: deps
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _auth(client) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"user-{uuid.uuid4().hex[:12]}@example.com",
            "password": "correct horse battery",
            "device_id": "dev-1",
        },
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_text_message_runs_agent_synchronously(client, deps):
    headers = await _auth(client)
    resp = await client.post("/api/v1/messages", json={"text": "2 boiled eggs"}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reply"] == "noted"
    assert body["actions"] == []
    call = deps.journal.calls[-1]
    assert call["message"] == "2 boiled eggs"
    # chat_id feeds the tool executor's int(chat_id) pinned-status path, so it
    # must stay numeric (the account id is the mobile conversation id).
    assert call["chat_id"].isdigit()


@pytest.mark.asyncio
async def test_apply_journal_actions_results_are_returned(client, deps):
    deps.journal.actions = [
        {
            "ok": True,
            "type": "CREATE",
            "entry": {"id": 42, "calories": 95, "eatenAt": "2026-10-12T08:30:00+00:00", "description": "un mar"},
            "date": "2026-10-12",
        },
        {"ok": False, "type": "EDIT", "message": "No matching journal entry exists."},
    ]
    headers = await _auth(client)
    resp = await client.post("/api/v1/messages", json={"text": "apple then fix it"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["actions"] == [
        {
            "ok": True,
            "type": "CREATE",
            "entry": {"id": 42, "calories": 95, "eaten_at": "2026-10-12T08:30:00+00:00", "description": "un mar"},
            "date": "2026-10-12",
            "message": None,
        },
        {
            "ok": False,
            "type": "EDIT",
            "entry": None,
            "date": None,
            "message": "No matching journal entry exists.",
        },
    ]


@pytest.mark.asyncio
async def test_audio_message_is_transcribed_then_run(client, deps):
    headers = await _auth(client)
    resp = await client.post(
        "/api/v1/messages",
        files={"audio": ("note.ogg", b"fake-opus-bytes", "audio/ogg")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert deps.voice.calls == [(b"fake-opus-bytes", "audio/ogg")]
    assert deps.journal.calls[-1]["message"] == "am mancat un mar"
    assert resp.json()["reply"] == "noted"


@pytest.mark.asyncio
async def test_audio_caption_is_appended_like_telegram(client, deps):
    headers = await _auth(client)
    resp = await client.post(
        "/api/v1/messages",
        files={"audio": ("note.m4a", b"fake-m4a", "audio/mp4")},
        data={"caption": "that was breakfast"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert deps.journal.calls[-1]["message"] == "am mancat un mar\nUser caption: that was breakfast"


@pytest.mark.asyncio
async def test_unauthenticated_is_401(client):
    resp = await client.post("/api/v1/messages", json={"text": "hi"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_oversize_audio_is_413(client, deps, monkeypatch):
    monkeypatch.setattr(messages, "MAX_VOICE_BYTES", 4)
    headers = await _auth(client)
    resp = await client.post(
        "/api/v1/messages",
        files={"audio": ("big.ogg", b"way-too-large-payload", "audio/ogg")},
        headers=headers,
    )
    assert resp.status_code == 413
    assert deps.voice.calls == []


@pytest.mark.asyncio
async def test_agent_failure_maps_to_502_without_internals(client, deps):
    deps.journal.failure = RuntimeError("secret internal detail")
    headers = await _auth(client)
    resp = await client.post("/api/v1/messages", json={"text": "2 eggs"}, headers=headers)
    assert resp.status_code == 502
    assert "secret internal detail" not in resp.text
    assert "RuntimeError" not in resp.text


@pytest.mark.asyncio
async def test_unsupported_content_type_is_415(client):
    headers = await _auth(client)
    resp = await client.post(
        "/api/v1/messages", content=b"hi", headers={**headers, "Content-Type": "text/plain"}
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_conversation_memory_records_the_turn(client, deps):
    headers = await _auth(client)
    resp = await client.post("/api/v1/messages", json={"text": "o cafea"}, headers=headers)
    assert resp.status_code == 200, resp.text

    from sqlalchemy import select

    from app.db.base import session_scope
    from app.db.models.conversation import ConversationMemory

    async with session_scope() as session:
        rows = (await session.execute(select(ConversationMemory).order_by(ConversationMemory.id))).scalars().all()
    assert [r.role for r in rows] == ["user", "assistant"]
    assert rows[0].content == "o cafea"
    assert rows[1].content == "noted"
