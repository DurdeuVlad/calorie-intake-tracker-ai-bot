"""End-to-end test of the agent loop + tool executor, using a stub model that
plays back a pre-programmed script instead of calling the real OpenAI API.
This exercises the exact same code path a real conversation would, just with
the LLM itself replaced.

v2.0: The model writes full replies from structured tool results. Tests assert
key facts in the reply (calories, undo mention) without requiring exact
template strings. The ScriptedModel provides a text reply after tool calls."""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.agent.journal_agent import JournalAgent
from app.agent.openai_model_client import AgentProviderUnavailableError
from app.db.base import session_scope
from app.db.models.entries import FoodEntry, FoodItem
from app.db.models.journal_changes import JournalChangeSet
from app.db.models.messaging import PinnedDailyStatus
from app.db.models.nutrition import NutritionEvidence, PendingNutritionQuote
from app.db.models.users import FoodUser, UserSettings
from app.domain.agent_types import AgentContext, AgentReply, ToolCall
from app.messaging import execution_context
from app.repositories import food_entry_repo, food_user_repo
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.services import daily_status_service
from app.services.journal_tool_executor import JournalToolExecutor


class ScriptedModel:
    """Returns one AgentReply per call to next(), in order."""

    def __init__(self, replies: list[AgentReply]) -> None:
        self._replies = list(replies)
        self.calls = 0

    async def next(self, context, memory, exchanges, feedback=None):
        reply = self._replies[self.calls]
        self.calls += 1
        return reply


class FailingModel:
    async def next(self, context, memory, exchanges, feedback=None):
        raise AgentProviderUnavailableError("simulated network failure")


class FailingAfterToolModel:
    def __init__(self, tool_call: ToolCall) -> None:
        self.tool_call = tool_call
        self.calls = 0

    async def next(self, context, memory, exchanges, feedback=None):
        self.calls += 1
        if self.calls == 1:
            return AgentReply(None, [self.tool_call])
        raise AgentProviderUnavailableError("simulated receipt-generation failure")


def _tool_call(tool_id: str, name: str, **arguments) -> ToolCall:
    return ToolCall(id=tool_id, name=name, arguments=json.dumps(arguments))


def _text_reply(text: str) -> AgentReply:
    return AgentReply(text, [])


async def _reload_user(session, user_id: int) -> FoodUser:
    return (await session.execute(select(FoodUser).where(FoodUser.id == user_id))).scalar_one()


@pytest.mark.asyncio
async def test_create_action_accepts_hour_only_local_time_from_a_natural_language_request():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "cafea", "calories": 20, "localTime": "9"}])],
            ),
            _text_reply("Notat: cafea — 20 kcal. Trimite Undo în 10 minute pentru a anula."),
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 110, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(
            session,
            AgentContext(user=user, chat_id="1", message="noteaza pe ora 9", started_at=started_at),
        )
        await session.commit()

    assert "cafea" in reply
    assert "20" in reply
    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalar_one()
    assert entry.eaten_at == datetime(2026, 4, 1, 6, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_create_action_logs_a_meal_and_model_writes_receipt():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "mic dejun", "calories": 600}])],
            ),
            _text_reply("Notat: mic dejun — 600 kcal. Trimite Undo în 10 minute."),
        ]
    )
    tools = JournalToolExecutor()
    agent = JournalAgent(model, tools, max_tool_calls=10)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 111, "Tester", "Europe/Bucharest")
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="mic dejun 600 kcal")
        reply = await agent.run(session, context)
        await session.commit()

    assert "mic dejun" in reply
    assert "600" in reply

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

    model1 = ScriptedModel([
        AgentReply(None, [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "salata", "calories": 300}])]),
        _text_reply("Notat: salata — 300 kcal."),
    ])
    agent1 = JournalAgent(model1, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await agent1.run(session, AgentContext(user=user, chat_id="1", message="salata 300 kcal"))
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry_id = entry.id
        assert entry.calories == 300

    model2 = ScriptedModel([
        AgentReply(None, [_tool_call("c2", "apply_journal_actions", actions=[{"type": "EDIT", "entryId": entry_id, "calories": 450}])]),
        _text_reply("Modificat: salata — 450 kcal. Undo disponibil 10 minute."),
    ])
    agent2 = JournalAgent(model2, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply2 = await agent2.run(session, AgentContext(user=user, chat_id="1", message="am fost 450 kcal de fapt"))
        await session.commit()
    assert "450" in reply2

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.calories == 450

    model3 = ScriptedModel([
        AgentReply(None, [_tool_call("c3", "undo_last_change")]),
        _text_reply("Anulat: salata (450 kcal)."),
    ])
    agent3 = JournalAgent(model3, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply3 = await agent3.run(session, AgentContext(user=user, chat_id="1", message="undo"))
        await session.commit()
    assert "salata" in reply3.lower() or "anulat" in reply3.lower()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.calories == 300


@pytest.mark.asyncio
async def test_move_requires_date_and_undo_preserves_nutrition_evidence():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 223, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    create_model = ScriptedModel([
        AgentReply(None, [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "description": "evidence meal", "calories": 200}])]),
        _text_reply("Logged evidence meal."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(create_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="evidence meal")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        item = (await session.execute(select(FoodItem).where(FoodItem.entry_id == entry.id))).scalar_one()
        original_when = entry.eaten_at
        session.add(
            NutritionEvidence(
                evidence_id=uuid.uuid4(),
                food_entry_id=entry.id,
                food_item_id=item.id,
                selected_quote_id=None,
                provider="open_food_facts",
                source_name="Open Food Facts",
                source_url="https://world.openfoodfacts.org/product/12345678",
                source_query="evidence meal",
                selected_candidate='{"name":"evidence meal"}',
                quantity_grams=Decimal("100.00"),
                calories_per_100g=200,
                total_calories=200,
                derivation="100 g × 200 kcal/100 g = 200 kcal",
                confidence="high",
                source_fetched_at=None,
                source_cache_hit=False,
                captured_at=datetime.now(UTC),
            )
        )
        await session.commit()
        entry_id = entry.id

    missing_date_model = ScriptedModel([
        AgentReply(None, [_tool_call("move-missing-date", "apply_journal_actions", actions=[{"type": "MOVE", "entryId": entry_id}])]),
        _text_reply("A date is required to move that entry."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply = await JournalAgent(missing_date_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="move it")
        )
        await session.commit()
    assert "required" in reply.lower()

    move_model = ScriptedModel([
        AgentReply(None, [_tool_call("move", "apply_journal_actions", actions=[{"type": "MOVE", "entryId": entry_id, "date": "yesterday"}])]),
        _text_reply("Moved the evidence meal."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(move_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="move it to yesterday")
        )
        await session.commit()

    undo_model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("Undone."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(undo_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        evidence = (await session.execute(select(NutritionEvidence).where(NutritionEvidence.food_entry_id == entry_id))).scalar_one()
        item = (await session.execute(select(FoodItem).where(FoodItem.id == evidence.food_item_id))).scalar_one()
        assert entry.eaten_at == original_when
        assert evidence.food_item_id == item.id
        assert evidence.total_calories == 200


@pytest.mark.asyncio
async def test_delete_is_soft_and_undo_restores_it():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 333, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    model1 = ScriptedModel([
        AgentReply(None, [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "gustare", "calories": 150}])]),
        _text_reply("Notat: gustare — 150 kcal."),
    ])
    agent1 = JournalAgent(model1, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await agent1.run(session, AgentContext(user=user, chat_id="1", message="gustare 150 kcal"))
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry_id = entry.id

    model2 = ScriptedModel([
        AgentReply(None, [_tool_call("c2", "apply_journal_actions", actions=[{"type": "DELETE", "entryId": entry_id}])]),
        _text_reply("Șters: gustare (150 kcal)."),
    ])
    agent2 = JournalAgent(model2, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply = await agent2.run(session, AgentContext(user=user, chat_id="1", message="sterge gustarea"))
        await session.commit()
    assert "gustare" in reply.lower()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.deleted_at is not None
        user = await _reload_user(session, user_id)
        found_active = await food_entry_repo.find_by_id_and_user(session, entry_id, user)
        assert found_active is None  # soft-deleted rows are excluded by default

    model3 = ScriptedModel([
        AgentReply(None, [_tool_call("c3", "undo_last_change")]),
        _text_reply("Anulat: ștergerea gustare (150 kcal)."),
    ])
    agent3 = JournalAgent(model3, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await agent3.run(session, AgentContext(user=user, chat_id="1", message="undo"))
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
        model = ScriptedModel([
            AgentReply(None, [_tool_call(tool_id, "apply_journal_actions", actions=[action])]),
            _text_reply("Done."),
        ])
        tools = JournalToolExecutor(refresh_daily_status=daily_status_service.refresh_for_tool_executor)
        agent = JournalAgent(model, tools, max_tool_calls=10)
        async with session_scope() as session:
            user = await _reload_user(session, user_id)
            await execution_context.run(lambda: agent.run(session, AgentContext(user=user, chat_id="334", message="update")))
            await session.commit()

    await run_action("create", {"type": "CREATE", "description": "meal", "calories": 100})
    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry_id = entry.id
        pinned = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user_id))).scalar_one()
        assert pinned.desired_version == 1 and "100 kcal" in pinned.desired_text

    await run_action("edit", {"type": "EDIT", "entryId": entry_id, "calories": 250})
    await run_action("delete", {"type": "DELETE", "entryId": entry_id})

    model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("Undone."),
    ])
    tools = JournalToolExecutor(refresh_daily_status=daily_status_service.refresh_for_tool_executor)
    agent = JournalAgent(model, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await execution_context.run(lambda: agent.run(session, AgentContext(user=user, chat_id="334", message="undo")))
        await session.commit()

    async with session_scope() as session:
        pinned = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user_id))).scalar_one()
        assert pinned.desired_version == 4
        assert pinned.delivered_version == 0
        assert "250 kcal" in pinned.desired_text


@pytest.mark.asyncio
async def test_pinned_status_failure_does_not_roll_back_journal_mutation():
    async def fail_refresh(session, user, chat_id):
        raise RuntimeError("simulated pinned status failure")

    model = ScriptedModel([
        AgentReply(
            None,
            [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "description": "status safe", "calories": 321}])],
        ),
        _text_reply("Logged status safe."),
    ])
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 567, "Tester", "Europe/Bucharest")
        await session.commit()
        tools = JournalToolExecutor(refresh_daily_status=fail_refresh)
        result = await JournalAgent(model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="status safe")
        )
        await session.commit()

    assert "Logged status safe" in result
    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.original_message == "status safe"))).scalars().all()
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_invalid_calories_are_retried_by_the_model_instead_of_surfaced_raw():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "orez", "calories": 999999}])],
            ),
            AgentReply(
                None,
                [_tool_call("c2", "apply_journal_actions", actions=[{"type": "CREATE", "description": "orez", "calories": 650}])],
            ),
            _text_reply("Logged: orez — 650 kcal."),
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 556, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="orez 50g"))
        await session.commit()

    assert model.calls == 3
    assert "orez" in reply
    assert "650" in reply
    assert "Calories must be" not in reply

    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert len(entries) == 1
    assert entries[0].calories == 650


@pytest.mark.asyncio
async def test_mixed_batch_model_writes_receipt_without_retrying():
    """v2.0: A partial failure must not re-loop the model to retry the batch.
    The model writes a receipt from the structured result on the next turn.
    The system prompt tells it not to resend the batch."""
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [
                    _tool_call(
                        "c1",
                        "apply_journal_actions",
                        actions=[
                            {"type": "CREATE", "description": "supa", "calories": 200},
                            {"type": "CREATE", "description": "prajitura", "calories": 999999},
                        ],
                    )
                ],
            ),
            _text_reply("Notat: supa — 200 kcal. prajitura a eșuat: calories invalid."),
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 557, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="supa 200 kcal si prajitura"))
        await session.commit()

    assert model.calls == 2  # tool call + text reply
    assert "supa" in reply
    assert "200" in reply

    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert len(entries) == 1
    assert entries[0].calories == 200


@pytest.mark.asyncio
async def test_update_settings_validation_is_atomic():
    executor = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 560, "Tester", "Europe/Bucharest")
        settings = await session.get(UserSettings, user.id)
        original_timezone = settings.timezone
        await session.commit()

        no_op = await executor.execute(
            session,
            AgentContext(user=user, chat_id="1", message="update settings"),
            _tool_call("settings-no-op", "update_settings"),
            [],
        )
        assert not no_op.ok

        result = await executor.execute(
            session,
            AgentContext(user=user, chat_id="1", message="update settings"),
            _tool_call("settings", "update_settings", timezone="UTC", calorieTarget=1),
            [],
        )
        assert not result.ok
        await session.commit()

    async with session_scope() as session:
        settings = await session.get(UserSettings, user.id)
        assert settings.timezone == original_timezone


@pytest.mark.asyncio
async def test_malformed_action_type_is_reported_without_aborting_successful_actions():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [
                    _tool_call(
                        "c1",
                        "apply_journal_actions",
                        actions=[
                            {"type": "CREATE", "description": "valid meal", "calories": 200},
                            {"type": 1, "description": "malformed meal", "calories": 300},
                        ],
                    )
                ],
            ),
            _text_reply("Logged the valid meal; the malformed action was rejected."),
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 559, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="mixed malformed batch"))
        await session.commit()

    assert "valid meal" in reply
    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert len(entries) == 1
    assert entries[0].calories == 200


@pytest.mark.asyncio
async def test_oversized_create_description_is_reported_as_validation_failure():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "x" * 256, "calories": 200}])],
            ),
            _text_reply("The description was too long."),
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 561, "Tester", "Europe/Bucharest")
        await session.commit()
        await agent.run(session, AgentContext(user=user, chat_id="1", message="long description"))
        await session.commit()

    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert entries == []


@pytest.mark.asyncio
async def test_hits_the_max_tool_call_limit():
    tool_calls = [_tool_call(f"c{i}", "get_today_summary") for i in range(5)]
    model = ScriptedModel([AgentReply(None, tool_calls)])
    tools = JournalToolExecutor()
    agent = JournalAgent(model, tools, max_tool_calls=2)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 444, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="anything"))
    assert "detail" in reply.lower()


@pytest.mark.asyncio
async def test_model_failure_returns_graceful_unavailable_reply():
    tools = JournalToolExecutor()
    agent = JournalAgent(FailingModel(), tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 555, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="hi"))
    assert "cannot process" in reply


@pytest.mark.asyncio
async def test_receipt_provider_failure_returns_structured_fallback_without_duplicate_retry():
    call = _tool_call(
        "create",
        "apply_journal_actions",
        actions=[{"type": "CREATE", "description": "fallback meal", "calories": 425}],
    )
    model = FailingAfterToolModel(call)
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 558, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="fallback meal"))
        await session.commit()

    assert model.calls == 2
    assert "fallback meal" in reply
    assert "425" in reply
    assert "Undo" in reply
    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert len(entries) == 1
    assert entries[0].calories == 425


@pytest.mark.asyncio
async def test_undo_expiry_race_is_reported_as_a_handled_tool_failure(monkeypatch):
    class ExpiringChangeSet:
        def __init__(self):
            self.id = 999999
            self.mutations = []

        def is_undoable_at(self, now):
            return True

        def mark_undone(self, now):
            raise ValueError("This change set can no longer be undone.")

    async def find_expiring_change_set(session, user, now):
        return ExpiringChangeSet()

    monkeypatch.setattr(
        "app.tools.journal_actions.journal_change_set_repo.find_first_undoable",
        find_expiring_change_set,
    )
    model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("The latest journal change can no longer be undone."),
    ])
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 565, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await JournalAgent(model, JournalToolExecutor(), max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    assert "can no longer be undone" in reply
    assert model.calls == 2


@pytest.mark.asyncio
async def test_undo_uses_execution_time_not_request_start_time(monkeypatch):
    observed: list[datetime] = []

    async def find_no_change(session, user, now):
        observed.append(now)

    monkeypatch.setattr(
        "app.tools.journal_actions.journal_change_set_repo.find_first_undoable",
        find_no_change,
    )
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 566, "Tester", "Europe/Bucharest")
        await session.commit()
        started_at = datetime.now(UTC) - timedelta(minutes=11)
        result = await JournalToolExecutor().execute(
            session,
            AgentContext(user=user, chat_id="1", message="undo", started_at=started_at),
            _tool_call("undo", "undo_last_change"),
            [],
        )

    assert not result.ok
    assert result.code == "NOT_FOUND"
    assert observed
    assert observed[0] > started_at + timedelta(minutes=10)


@pytest.mark.asyncio
async def test_undo_refuses_to_overwrite_an_intervening_entry_change():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 562, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    create_model = ScriptedModel([
        AgentReply(None, [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "description": "original", "calories": 200}])]),
        _text_reply("Logged original."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(create_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="original")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry.revise("intervening change", 999)
        await session.commit()

    undo_model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("The change could not be undone safely."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply = await JournalAgent(undo_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    assert "could not be undone" in reply
    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        assert entry.original_message == "intervening change"
        assert entry.calories == 999


@pytest.mark.asyncio
async def test_undo_handles_multiple_mutations_of_the_same_entry_in_one_batch():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 563, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    create_model = ScriptedModel([
        AgentReply(None, [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "description": "same entry", "calories": 200}])]),
        _text_reply("Logged same entry."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(create_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="same entry")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry_id = entry.id
        original_when = entry.eaten_at

    update_model = ScriptedModel([
        AgentReply(
            None,
            [_tool_call(
                "update",
                "apply_journal_actions",
                actions=[
                    {"type": "EDIT", "entryId": entry_id, "description": "edited entry", "calories": 300},
                    {"type": "MOVE", "entryId": entry_id, "date": "yesterday"},
                ],
            )],
        ),
        _text_reply("Updated same entry."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(update_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="edit and move")
        )
        await session.commit()

    undo_model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("Undone."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(undo_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.original_message == "same entry"
        assert entry.calories == 200
        assert entry.eaten_at == original_when


@pytest.mark.asyncio
async def test_journal_mutations_serialize_per_user_before_undo_selects_latest_change():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 564, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    create_model = ScriptedModel([
        AgentReply(None, [_tool_call("initial", "apply_journal_actions", actions=[{"type": "CREATE", "description": "initial", "calories": 100}])]),
        _text_reply("Logged initial."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(create_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="initial")
        )
        await session.commit()

    async def create_concurrent_entry() -> None:
        model = ScriptedModel([
            AgentReply(None, [_tool_call("concurrent", "apply_journal_actions", actions=[{"type": "CREATE", "description": "concurrent", "calories": 200}])]),
            _text_reply("Logged concurrent."),
        ])
        async with session_scope() as session:
            user = await _reload_user(session, user_id)
            await JournalAgent(model, tools, max_tool_calls=10).run(
                session, AgentContext(user=user, chat_id="1", message="concurrent")
            )
            await session.commit()

    async with session_scope() as holder:
        await food_user_repo.lock_for_journal_mutation(holder, user_id)
        concurrent_task = asyncio.create_task(create_concurrent_entry())
        await asyncio.sleep(0.1)
        assert not concurrent_task.done()
        await holder.commit()
        await asyncio.wait_for(concurrent_task, timeout=5)

    async with session_scope() as session:
        entries = (
            await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id).order_by(FoodEntry.id))
        ).scalars().all()
        assert [entry.original_message for entry in entries] == ["initial", "concurrent"]

    undo_model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("Undone."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(undo_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    async with session_scope() as session:
        entries = (
            await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id).order_by(FoodEntry.id))
        ).scalars().all()
        assert entries[0].deleted_at is None
        assert entries[1].deleted_at is not None


@pytest.mark.asyncio
async def test_new_change_set_undo_window_starts_when_mutation_executes():
    model = ScriptedModel([
        AgentReply(
            None,
            [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "description": "slow meal", "calories": 150}])],
        ),
        _text_reply("Logged slow meal."),
    ])
    started_at = datetime.now(UTC) - timedelta(minutes=11)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 5678, "Tester", "Europe/Bucharest")
        await session.commit()
        await JournalAgent(model, JournalToolExecutor(), max_tool_calls=10).run(
            session,
            AgentContext(user=user, chat_id="1", message="slow meal", started_at=started_at),
        )
        await session.commit()
        change_set = (
            await session.execute(
                select(JournalChangeSet).where(JournalChangeSet.user_id == user.id)
            )
        ).scalar_one()

    assert change_set.created_at > started_at + timedelta(minutes=10)
    assert change_set.expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_ai_estimate_evidence_survives_edit_and_undo():
    tools = JournalToolExecutor()
    now = datetime.now(UTC)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 5680, "Tester", "Europe/Bucharest")
        quote = PendingNutritionQuote(
            quote_id=uuid.uuid4(), batch_id=uuid.uuid4(), user_id=user.id, quote_type="AI_ESTIMATE",
            product_name="estimated curry", grams=Decimal("250.00"), calories_per_100g=200,
            estimate_basis="visible bowl portion", created_at=now, expires_at=now + timedelta(minutes=30),
        )
        session.add(quote)
        quote_id = quote.quote_id
        user_id = user.id
        await session.commit()

    create_model = ScriptedModel([
        AgentReply(None, [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "quoteId": str(quote_id)}])]),
        _text_reply("Prepared and logged estimated curry."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(create_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="log the estimate")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        evidence = (await session.execute(select(NutritionEvidence).where(NutritionEvidence.food_entry_id == entry.id))).scalar_one()
        assert evidence.provider == "ai_estimate"
        assert evidence.selected_quote_id == quote_id
        assert evidence.source_name == "AI estimate"
        entry_id = entry.id

    edit_model = ScriptedModel([
        AgentReply(None, [_tool_call("edit", "apply_journal_actions", actions=[{"type": "EDIT", "entryId": entry_id, "calories": 450}])]),
        _text_reply("Updated estimated curry."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(edit_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="adjust estimate")
        )
        await session.commit()

    undo_model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("Undone."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(undo_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        evidence = (await session.execute(select(NutritionEvidence).where(NutritionEvidence.food_entry_id == entry_id))).scalar_one()
        assert entry.calories == 500
        assert evidence.provider == "ai_estimate"
        assert evidence.selected_quote_id == quote_id
        assert evidence.derivation == "250.00 g × 200 kcal/100 g = 500 kcal"


@pytest.mark.asyncio
async def test_malformed_undo_snapshot_returns_conflict_without_mutating_state():
    now = datetime.now(UTC)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 5690, "Tester", "Europe/Bucharest")
        entry = FoodEntry(
            user_id=user.id,
            original_message="snapshot meal",
            eaten_at=now,
            calories=200,
            nutrition_source="manual",
            confidence="high",
            created_at=now,
        )
        session.add(entry)
        await session.flush()

        change_set = JournalChangeSet(
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(minutes=10),
        )
        change_set.add_mutation(
            "EDIT",
            {"entryId": entry.id},
            {
                "entryId": entry.id,
                "originalMessage": entry.original_message,
                "eatenAt": entry.eaten_at.isoformat(),
                "calories": entry.calories,
                "nutritionSource": entry.nutrition_source,
                "confidence": entry.confidence,
                "deletedAt": None,
                "items": [],
            },
        )
        session.add(change_set)
        await session.commit()
        user_id = user.id
        entry_id = entry.id

    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        result = await JournalToolExecutor().execute(
            session,
            AgentContext(user=user, chat_id="1", message="undo"),
            _tool_call("undo", "undo_last_change"),
            [],
        )
        await session.commit()

    assert not result.ok
    assert result.code == "CONFLICT"
    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        change_set = (
            await session.execute(select(JournalChangeSet).where(JournalChangeSet.user_id == user_id))
        ).scalar_one()
        assert entry.original_message == "snapshot meal"
        assert entry.calories == 200
        assert change_set.undone_at is None
