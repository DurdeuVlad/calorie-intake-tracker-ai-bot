"""Companion memory (audit section 4.4): durable user-scoped facts saved and
forgotten through the save_memory/forget_memory agent tools, listed and
deleted through GET/DELETE /api/v1/memories. Exercises the same agent loop +
tool executor path as test_journal_agent_apply_actions, with a scripted model
standing in for the LLM."""

import json
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agent.journal_agent import JournalAgent
from app.db.base import session_scope
from app.db.models.companion import CompanionMemory
from app.db.models.users import FoodUser
from app.domain.agent_types import AgentContext, AgentReply, ToolCall
from app.main import create_app
from app.mobile.rate_limit import limiter
from app.repositories import companion_memory_repo
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.services.journal_tool_executor import JournalToolExecutor


class ScriptedModel:
    def __init__(self, replies: list[AgentReply]) -> None:
        self._replies = list(replies)
        self.calls = 0

    async def next(self, context, memory, exchanges):
        reply = self._replies[self.calls]
        self.calls += 1
        return reply


def _tool_call(tool_id: str, name: str, **arguments) -> ToolCall:
    return ToolCall(id=tool_id, name=name, arguments=json.dumps(arguments))


def _agent(model) -> JournalAgent:
    return JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)


async def _run(agent: JournalAgent, user_id: int, message: str) -> str:
    async with session_scope() as session:
        user = (await session.execute(select(FoodUser).where(FoodUser.id == user_id))).scalar_one()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", romanian=False, message=message))
        await session.commit()
        return reply


async def _active_rows(user_id: int) -> list[CompanionMemory]:
    async with session_scope() as session:
        stmt = select(CompanionMemory).where(
            CompanionMemory.user_id == user_id, CompanionMemory.deleted_at.is_(None)
        )
        return list((await session.execute(stmt)).scalars().all())


@pytest_asyncio.fixture
async def user_id() -> int:
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 777001, "Tester", "Europe/Bucharest")
        await session.commit()
        return user.id


# --- agent tool path -------------------------------------------------------


@pytest.mark.asyncio
async def test_save_memory_writes_a_scoped_row(user_id):
    agent = _agent(
        ScriptedModel(
            [
                AgentReply(
                    None,
                    [_tool_call("c1", "save_memory", kind="preference", text="dislikes cilantro")],
                ),
                AgentReply("Got it.", []),
            ]
        )
    )
    await _run(agent, user_id, "remember that I hate cilantro")

    rows = await _active_rows(user_id)
    assert len(rows) == 1
    assert rows[0].kind == "preference"
    assert rows[0].text == "dislikes cilantro"
    assert rows[0].source == "agent"
    assert rows[0].user_id == user_id


@pytest.mark.asyncio
async def test_save_memory_dedupes_normalized_text(user_id):
    tools = JournalToolExecutor()

    async with session_scope() as session:
        user = (await session.execute(select(FoodUser).where(FoodUser.id == user_id))).scalar_one()
        context = AgentContext(user=user, chat_id="1", romanian=False, message="x")
        first = await tools.execute(
            session, context, _tool_call("a", "save_memory", kind="goal", text="targets  160g protein"), []
        )
        # Same fact, different casing/whitespace/kind -> same row, not a second insert.
        second = await tools.execute(
            session, context, _tool_call("b", "save_memory", kind="fact", text="  Targets 160g Protein "), []
        )
        await session.commit()

    assert first.ok and second.ok
    assert first.data["alreadyKnown"] is False
    assert second.data["alreadyKnown"] is True
    assert second.data["memoryId"] == first.data["memoryId"]

    rows = await _active_rows(user_id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_forget_memory_by_id_and_by_text(user_id):
    tools = JournalToolExecutor()

    async with session_scope() as session:
        user = (await session.execute(select(FoodUser).where(FoodUser.id == user_id))).scalar_one()
        context = AgentContext(user=user, chat_id="1", romanian=False, message="x")
        saved1 = await tools.execute(
            session, context, _tool_call("a", "save_memory", text="allergic to peanuts"), []
        )
        saved2 = await tools.execute(
            session, context, _tool_call("b", "save_memory", text="prefers low-carb dinners"), []
        )
        memory_id = saved1.data["memoryId"]

        by_id = await tools.execute(
            session, context, _tool_call("c", "forget_memory", memoryId=memory_id), []
        )
        assert by_id.ok and by_id.data["forgotten"] is True

        # Substring/case-insensitive match, not exact text.
        by_text = await tools.execute(
            session, context, _tool_call("d", "forget_memory", text="LOW-CARB"), []
        )
        assert by_text.ok
        assert by_text.data["memoryId"] == saved2.data["memoryId"]

        gone = await tools.execute(
            session, context, _tool_call("e", "forget_memory", memoryId=memory_id), []
        )
        assert not gone.ok and gone.code == "NOT_FOUND"

        missing = await tools.execute(
            session, context, _tool_call("f", "forget_memory", text="cilantro"), []
        )
        assert not missing.ok and missing.code == "NOT_FOUND"
        await session.commit()

    assert await _active_rows(user_id) == []


@pytest.mark.asyncio
async def test_forget_memory_requires_an_identifier(user_id):
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = (await session.execute(select(FoodUser).where(FoodUser.id == user_id))).scalar_one()
        context = AgentContext(user=user, chat_id="1", romanian=False, message="x")
        result = await tools.execute(session, context, _tool_call("a", "forget_memory"), [])
        assert not result.ok and result.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_tools_never_cross_users():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        owner = await get_or_create_by_telegram_user_id(session, 777002, "Owner", "Europe/Bucharest")
        other = await get_or_create_by_telegram_user_id(session, 777003, "Other", "Europe/Bucharest")
        await session.flush()
        owner_id, other_id = owner.id, other.id

        saved = await tools.execute(
            session,
            AgentContext(user=owner, chat_id="1", romanian=False, message="x"),
            _tool_call("a", "save_memory", text="owner secret"),
            [],
        )
        memory_id = saved.data["memoryId"]

        other_context = AgentContext(user=other, chat_id="1", romanian=False, message="x")
        by_id = await tools.execute(session, other_context, _tool_call("b", "forget_memory", memoryId=memory_id), [])
        by_text = await tools.execute(session, other_context, _tool_call("c", "forget_memory", text="owner secret"), [])
        assert not by_id.ok and by_id.code == "NOT_FOUND"
        assert not by_text.ok and by_text.code == "NOT_FOUND"
        await session.commit()

    rows = await _active_rows(owner_id)
    assert len(rows) == 1  # still there for the real owner


# --- mobile endpoints --------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_rate_limiter(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "mobile_auth_rate_limit_per_minute", 10_000)
    monkeypatch.setattr(settings, "mobile_message_rate_limit_per_minute", 10_000)
    limiter.reset()
    yield
    limiter.reset()


@pytest_asyncio.fixture
async def client():
    app = create_app()
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


async def _food_user_id(client, headers) -> int:
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["food_user_id"]


@pytest.mark.asyncio
async def test_memories_require_auth(client):
    assert (await client.get("/api/v1/memories")).status_code == 401
    assert (await client.delete("/api/v1/memories/1")).status_code == 401


@pytest.mark.asyncio
async def test_list_and_delete_are_scoped_to_the_caller(client):
    headers_a = await _auth(client)
    headers_b = await _auth(client)
    user_a = await _food_user_id(client, headers_a)

    # Seed one memory for user A directly through the repo (same path the tool uses).
    async with session_scope() as session:
        user = (await session.execute(select(FoodUser).where(FoodUser.id == user_a))).scalar_one()
        row, created = await companion_memory_repo.save(session, user, "preference", "dislikes cilantro", source="agent")
        assert created
        memory_id = row.id
        await session.commit()

    # User A sees it; user B sees nothing and cannot delete it.
    resp = await client.get("/api/v1/memories", headers=headers_a)
    assert resp.status_code == 200, resp.text
    memories = resp.json()["memories"]
    assert [m["id"] for m in memories] == [memory_id]
    assert memories[0]["text"] == "dislikes cilantro"
    assert memories[0]["source"] == "agent"

    resp = await client.get("/api/v1/memories", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json()["memories"] == []

    assert (await client.delete(f"/api/v1/memories/{memory_id}", headers=headers_b)).status_code == 404
    assert (await client.get("/api/v1/memories", headers=headers_a)).json()["memories"] != []

    # The owner can delete; afterwards it is gone from the list and re-deleting is 404.
    assert (await client.delete(f"/api/v1/memories/{memory_id}", headers=headers_a)).status_code == 204
    assert (await client.get("/api/v1/memories", headers=headers_a)).json()["memories"] == []
    assert (await client.delete(f"/api/v1/memories/{memory_id}", headers=headers_a)).status_code == 404
