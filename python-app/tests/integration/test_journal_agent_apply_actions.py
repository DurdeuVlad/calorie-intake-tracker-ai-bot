"""End-to-end test of the agent loop + tool executor + canonical reply
rendering, using a stub model that plays back a pre-programmed script instead
of calling the real OpenAI API. This exercises the exact same code path a
real conversation would, just with the LLM itself replaced."""

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.agent.journal_agent import JournalAgent
from app.agent.openai_model_client import AgentProviderUnavailableError
from app.db.base import session_scope
from app.db.models.entries import FoodEntry
from app.db.models.messaging import PinnedDailyStatus
from app.db.models.users import FoodUser
from app.domain.agent_types import AgentContext, AgentReply, ToolCall
from app.messaging import execution_context
from app.repositories import food_entry_repo
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.services import daily_status_service
from app.services.journal_tool_executor import JournalToolExecutor


class ScriptedModel:
    """Returns one AgentReply per call to next(), in order."""

    def __init__(self, replies: list[AgentReply]) -> None:
        self._replies = list(replies)
        self.calls = 0

    async def next(self, context, memory, exchanges):
        reply = self._replies[self.calls]
        self.calls += 1
        return reply


class FailingModel:
    async def next(self, context, memory, exchanges):
        raise AgentProviderUnavailableError("simulated network failure")


def _tool_call(tool_id: str, name: str, **arguments) -> ToolCall:
    return ToolCall(id=tool_id, name=name, arguments=json.dumps(arguments))


async def _reload_user(session, user_id: int) -> FoodUser:
    return (await session.execute(select(FoodUser).where(FoodUser.id == user_id))).scalar_one()


@pytest.mark.asyncio
async def test_create_action_accepts_hour_only_local_time_from_a_natural_language_request():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "cafea", "calories": 20, "localTime": "9"}])],
            )
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 110, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(
            session,
            AgentContext(user=user, chat_id="1", romanian=True, message="noteaza pe ora 9", started_at=started_at),
        )
        await session.commit()

    assert "Logged: cafea" in reply
    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalar_one()
    assert entry.eaten_at == datetime(2026, 4, 1, 6, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_create_action_logs_a_meal_and_reports_it_canonically():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "mic dejun", "calories": 600}])],
            )
        ]
    )
    tools = JournalToolExecutor()
    agent = JournalAgent(model, tools, max_tool_calls=10)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 111, "Tester", "Europe/Bucharest")
        await session.commit()
        context = AgentContext(user=user, chat_id="1", romanian=True, message="mic dejun 600 kcal")
        reply = await agent.run(session, context)
        await session.commit()

    assert "Logged: mic dejun" in reply
    assert "600 kcal" in reply

    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert len(entries) == 1
    assert entries[0].calories == 600


@pytest.mark.asyncio
async def test_create_then_edit_then_undo_restores_the_original_entry():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 222, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    model1 = ScriptedModel([AgentReply(None, [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "salata", "calories": 300}])])])
    agent1 = JournalAgent(model1, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await agent1.run(session, AgentContext(user=user, chat_id="1", romanian=True, message="salata 300 kcal"))
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry_id = entry.id
        assert entry.calories == 300

    model2 = ScriptedModel([AgentReply(None, [_tool_call("c2", "apply_journal_actions", actions=[{"type": "EDIT", "entryId": entry_id, "calories": 450}])])])
    agent2 = JournalAgent(model2, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply2 = await agent2.run(session, AgentContext(user=user, chat_id="1", romanian=True, message="am fost 450 kcal de fapt"))
        await session.commit()
    assert "Modificat" in reply2
    assert "Undo" in reply2

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.calories == 450

    model3 = ScriptedModel([AgentReply(None, [_tool_call("c3", "undo_last_change")])])
    agent3 = JournalAgent(model3, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply3 = await agent3.run(session, AgentContext(user=user, chat_id="1", romanian=True, message="undo"))
        await session.commit()
    assert "anulat" in reply3.lower()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.calories == 300


@pytest.mark.asyncio
async def test_delete_is_soft_and_undo_restores_it():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 333, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    model1 = ScriptedModel([AgentReply(None, [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "gustare", "calories": 150}])])])
    agent1 = JournalAgent(model1, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await agent1.run(session, AgentContext(user=user, chat_id="1", romanian=True, message="gustare 150 kcal"))
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry_id = entry.id

    model2 = ScriptedModel([AgentReply(None, [_tool_call("c2", "apply_journal_actions", actions=[{"type": "DELETE", "entryId": entry_id}])])])
    agent2 = JournalAgent(model2, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply = await agent2.run(session, AgentContext(user=user, chat_id="1", romanian=True, message="sterge gustarea"))
        await session.commit()
    assert "Șters" in reply

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.deleted_at is not None
        user = await _reload_user(session, user_id)
        found_active = await food_entry_repo.find_by_id_and_user(session, entry_id, user)
        assert found_active is None  # soft-deleted rows are excluded by default

    model3 = ScriptedModel([AgentReply(None, [_tool_call("c3", "undo_last_change")])])
    agent3 = JournalAgent(model3, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await agent3.run(session, AgentContext(user=user, chat_id="1", romanian=True, message="undo"))
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.deleted_at is None


@pytest.mark.asyncio
async def test_create_edit_delete_and_undo_mark_the_pinned_total_dirty_inside_message_execution():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 334, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    async def run_action(tool_id, action):
        model = ScriptedModel([AgentReply(None, [_tool_call(tool_id, "apply_journal_actions", actions=[action])])])
        tools = JournalToolExecutor(refresh_daily_status=daily_status_service.refresh_for_tool_executor)
        agent = JournalAgent(model, tools, max_tool_calls=10)
        async with session_scope() as session:
            user = await _reload_user(session, user_id)
            await execution_context.run(lambda: agent.run(session, AgentContext(user=user, chat_id="334", romanian=False, message="update")))
            await session.commit()

    await run_action("create", {"type": "CREATE", "description": "meal", "calories": 100})
    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry_id = entry.id
        pinned = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user_id))).scalar_one()
        assert pinned.desired_version == 1 and "100 kcal" in pinned.desired_text

    await run_action("edit", {"type": "EDIT", "entryId": entry_id, "calories": 250})
    await run_action("delete", {"type": "DELETE", "entryId": entry_id})

    model = ScriptedModel([AgentReply(None, [_tool_call("undo", "undo_last_change")])])
    tools = JournalToolExecutor(refresh_daily_status=daily_status_service.refresh_for_tool_executor)
    agent = JournalAgent(model, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await execution_context.run(lambda: agent.run(session, AgentContext(user=user, chat_id="334", romanian=False, message="undo")))
        await session.commit()

    async with session_scope() as session:
        pinned = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user_id))).scalar_one()
        assert pinned.desired_version == 4
        assert pinned.delivered_version == 0
        assert "250 kcal" in pinned.desired_text


@pytest.mark.asyncio
async def test_hits_the_max_tool_call_limit():
    tool_calls = [_tool_call(f"c{i}", "get_today_summary") for i in range(5)]
    model = ScriptedModel([AgentReply(None, tool_calls)])
    tools = JournalToolExecutor()
    agent = JournalAgent(model, tools, max_tool_calls=2)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 444, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", romanian=False, message="anything"))
    assert "detail" in reply.lower()


@pytest.mark.asyncio
async def test_model_failure_returns_graceful_unavailable_reply():
    tools = JournalToolExecutor()
    agent = JournalAgent(FailingModel(), tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 555, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", romanian=False, message="hi"))
    assert "cannot process" in reply
