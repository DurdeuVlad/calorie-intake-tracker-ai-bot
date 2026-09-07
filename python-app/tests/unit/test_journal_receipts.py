"""v2.0 receipt tests: assert structured tool results contain the right data
(calories, source, derivation, undo deadline) rather than testing the
deterministic renderer (which was removed in issue #98)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.models.nutrition import NutritionEvidence
from app.domain.agent_types import (
    AgentContext,
    AgentExchange,
    AgentToolFailure,
    AgentToolResult,
    ToolCall,
)
from app.terminal.trace_collector import TerminalTraceCollector


def _context(**kwargs) -> AgentContext:
    defaults = {"user": None, "chat_id": "1", "message": "meal"}
    defaults.update(kwargs)
    return AgentContext(**defaults)


def _evidence(**kwargs) -> NutritionEvidence:
    values = {
        "evidence_id": uuid.uuid4(), "food_entry_id": 1, "food_item_id": 2, "provider": "open_food_facts",
        "source_name": "Open Food Facts", "source_url": "https://world.openfoodfacts.org/product/123",
        "selected_candidate": '{"name":"Greek yogurt","brand":"Acme","barcode":"123"}',
        "quantity_grams": Decimal(150), "calories_per_100g": 97, "total_calories": 146,
        "derivation": "round(150 g × 97 kcal / 100 g) = 146 kcal", "confidence": "high",
        "source_fetched_at": datetime.now(UTC), "source_cache_hit": False, "captured_at": datetime.now(UTC),
    }
    values.update(kwargs)
    return NutritionEvidence(**values)


# --- Structured tool result assertions (issue #97) -----------------------

def test_action_success_includes_receipt_ready_fields():
    from app.db.models.entries import FoodEntry
    from app.services.journal_tool_executor import JournalToolExecutor

    entry = FoodEntry(
        id=1, user_id=1, original_message="yogurt", eaten_at=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
        calories=146, nutrition_source="open_food_facts", confidence="high", created_at=datetime.now(UTC),
    )
    executor = JournalToolExecutor()
    undo_deadline = datetime.now(UTC) + timedelta(minutes=10)
    result = executor._action_success(
        "CREATE", entry, "Europe/Bucharest",
        receipt={"quantity": 150, "unit": "g"},
        undo_deadline=undo_deadline,
        derivation="round(150 g × 97 kcal / 100 g) = 146 kcal",
        source_url="https://world.openfoodfacts.org/product/123",
        source_name="Open Food Facts",
    )
    assert result["ok"] is True
    assert result["type"] == "CREATE"
    assert result["calories"] == 146
    assert result["description"] == "yogurt"
    assert result["nutritionSource"] == "open_food_facts"
    assert result["nutritionConfidence"] == "high"
    assert result["derivation"] == "round(150 g × 97 kcal / 100 g) = 146 kcal"
    assert result["undoDeadline"] == undo_deadline.isoformat()
    assert result["sourceUrl"] == "https://world.openfoodfacts.org/product/123"
    assert result["sourceName"] == "Open Food Facts"
    assert result["receipt"] == {"quantity": 150, "unit": "g"}


def test_action_success_without_optional_fields_omits_them():
    from app.db.models.entries import FoodEntry
    from app.services.journal_tool_executor import JournalToolExecutor

    entry = FoodEntry(
        id=2, user_id=1, original_message="toast", eaten_at=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
        calories=120, nutrition_source="manual", confidence="high", created_at=datetime.now(UTC),
    )
    result = JournalToolExecutor()._action_success("CREATE", entry, "Europe/Bucharest")
    assert "derivation" not in result
    assert "undoDeadline" not in result
    assert "sourceUrl" not in result
    assert "sourceName" not in result
    assert "receipt" not in result
    assert result["calories"] == 120
    assert result["description"] == "toast"


@pytest.mark.parametrize("action_name", ["apply_journal_actions", "undo_last_change"])
def test_fallback_receipt_does_not_report_an_undone_mutation(action_name):
    from app.agent.journal_agent import JournalAgent

    apply_result = AgentToolResult.success({
        "successful": 1,
        "results": [{"ok": True, "type": "CREATE", "description": "meal", "calories": 100}],
        "undoAvailable": True,
    })
    exchanges = [AgentExchange(ToolCall("create", "apply_journal_actions", "{}"), apply_result)]
    if action_name == "undo_last_change":
        exchanges.append(
            AgentExchange(
                ToolCall("undo", "undo_last_change", "{}"),
                AgentToolResult.success({"undoneActions": [{"description": "meal", "calories": 100}]}),
            )
        )

    receipt = JournalAgent(None, None, 10)._fallback_receipt(exchanges)

    assert receipt is not None
    if action_name == "undo_last_change":
        assert "Undid" in receipt
        assert "Logged" not in receipt
    else:
        assert "Logged: meal" in receipt


def test_fallback_receipt_acknowledges_durable_non_journal_tools():
    from app.agent.journal_agent import JournalAgent

    exchanges = [
        AgentExchange(
            ToolCall("quote", "search_packaged_food", "{}"),
            AgentToolResult.success({"products": [{"name": "cereal"}, {"name": "oats"}]}),
        ),
        AgentExchange(
            ToolCall("settings", "update_settings", "{}"),
            AgentToolResult.success({"timezone": "UTC", "updated": True}),
        ),
    ]

    receipt = JournalAgent(None, None, 10)._fallback_receipt(exchanges)

    assert receipt is not None
    assert "Found 2 packaged nutrition choices" in receipt
    assert "Updated your settings" in receipt
    assert "try again" not in receipt.lower()


def test_fallback_receipt_does_not_acknowledge_noop_settings_result():
    from app.agent.journal_agent import JournalAgent

    exchanges = [
        AgentExchange(
            ToolCall("settings", "update_settings", "{}"),
            AgentToolResult.success({"timezone": "UTC"}),
        )
    ]

    assert JournalAgent(None, None, 10)._fallback_receipt(exchanges) is None


def test_fallback_receipt_aggregates_durable_work_after_undo_and_journal_success():
    from app.agent.journal_agent import JournalAgent

    exchanges = [
        AgentExchange(
            ToolCall("create", "apply_journal_actions", "{}"),
            AgentToolResult.success({
                "successful": 1,
                "results": [{"ok": True, "type": "CREATE", "description": "meal", "calories": 100}],
                "undoAvailable": True,
            }),
        ),
        AgentExchange(
            ToolCall("undo", "undo_last_change", "{}"),
            AgentToolResult.success({"undoneActions": [{"description": "meal", "calories": 100}]}),
        ),
        AgentExchange(
            ToolCall("alias", "save_alias", "{}"),
            AgentToolResult.success({"message": "Saved alias 'oats'."}),
        ),
        AgentExchange(
            ToolCall("create2", "apply_journal_actions", "{}"),
            AgentToolResult.success({
                "successful": 1,
                "results": [{"ok": True, "type": "CREATE", "description": "new meal", "calories": 200}],
                "undoAvailable": True,
            }),
        ),
    ]

    receipt = JournalAgent(None, None, 10)._fallback_receipt(exchanges)

    assert receipt is not None
    assert "Undid: meal (100 kcal)" in receipt
    assert "Saved alias 'oats'." in receipt
    assert "Logged: new meal — 200 kcal." in receipt
    assert "Logged: meal" not in receipt


def test_fallback_receipt_limits_undo_claim_to_latest_mutation_batch():
    from app.agent.journal_agent import JournalAgent

    exchanges = [
        AgentExchange(
            ToolCall("create1", "apply_journal_actions", "{}"),
            AgentToolResult.success({
                "successful": 1,
                "results": [{"ok": True, "type": "CREATE", "description": "first meal", "calories": 100}],
                "undoAvailable": True,
            }),
        ),
        AgentExchange(
            ToolCall("create2", "apply_journal_actions", "{}"),
            AgentToolResult.success({
                "successful": 1,
                "results": [{"ok": True, "type": "CREATE", "description": "second meal", "calories": 200}],
                "undoAvailable": True,
            }),
        ),
    ]

    receipt = JournalAgent(None, None, 10)._fallback_receipt(exchanges)

    assert receipt is not None
    assert "only the latest successful change batch" in receipt


@pytest.mark.asyncio
async def test_daily_status_adapter_ignores_opaque_non_telegram_chat_ids(monkeypatch):
    from app.services import daily_status_service

    called = False

    async def fail_if_called(session, user, chat_id):
        nonlocal called
        called = True

    monkeypatch.setattr(daily_status_service, "refresh", fail_if_called)
    await daily_status_service.refresh_for_tool_executor(None, None, "mattermost-channel")
    assert not called


def test_shared_tool_validation_rejects_oversized_text_and_numeric_boundaries():
    from app.tools.shared import (
        MAX_DATABASE_ID,
        MAX_GRAMS,
        ValidationError,
        _decimal_number,
        _int_required,
        _quantity_number,
        _text,
    )

    with pytest.raises(ValidationError):
        _text({"description": "x" * 256}, "description", 255)
    with pytest.raises(ValidationError):
        _text({"description": "meal\nwith control"}, "description", 255)
    with pytest.raises(ValidationError):
        _decimal_number({"grams": MAX_GRAMS + 1}, "grams", min_value=0, max_value=MAX_GRAMS)
    with pytest.raises(ValidationError):
        _decimal_number({"grams": 0}, "grams", min_value=0, max_value=MAX_GRAMS, exclusive_min_value=0)
    with pytest.raises(ValidationError):
        _int_required({"entryId": MAX_DATABASE_ID + 1}, "entryId", min_value=1, max_value=MAX_DATABASE_ID)
    with pytest.raises(ValidationError):
        _quantity_number({"grams": 0.001}, "grams")
    assert _quantity_number({"grams": 1.25}, "grams") == 1.25


# --- Undo result includes undone actions (issue #97) ---------------------

def test_undo_result_structure_has_undone_actions():
    """The undo tool result must include undoneActions with descriptions and
    calories so the model can write 'Undid: yogurt (146 kcal)'."""
    result = AgentToolResult.success({
        "changeSetId": 42,
        "actions": 2,
        "undoneActions": [
            {"type": "CREATE", "description": "yogurt", "calories": 146},
            {"type": "EDIT", "description": "toast", "calories": 200},
        ],
    })
    assert result.ok
    undone = result.data["undoneActions"]
    assert len(undone) == 2
    assert undone[0]["description"] == "yogurt"
    assert undone[0]["calories"] == 146
    assert undone[1]["description"] == "toast"
    assert undone[1]["calories"] == 200


# --- Media context is passed to the model (issue #98) --------------------

def test_user_content_includes_voice_transcript():
    from app.agent.openai_model_client import _user_content

    content = _user_content(_context(
        message="noteaza",
        media_kind="voice",
        media_text="two eggs and toast",
    ))
    assert "noteaza" in content
    assert "two eggs and toast" in content
    assert "Server transcript" in content


def test_user_content_includes_photo_interpretation():
    from app.agent.openai_model_client import _user_content

    content = _user_content(_context(
        message="cat de multe calorii",
        media_kind="photo",
        media_text="Interpretation: rice bowl with chicken\nEstimate: 500 kcal",
    ))
    assert "cat de multe calorii" in content
    assert "rice bowl with chicken" in content
    assert "Photo interpretation" in content


def test_user_content_without_media_is_just_the_message():
    from app.agent.openai_model_client import _user_content

    content = _user_content(_context(message="hello"))
    assert content == "hello"


# --- run_undo trace tests (kept from v1, adapted for v2) -----------------

class _StubTools:
    """Stand-in for JournalToolExecutor that returns a canned result without
    touching the database -- run_undo's contract is "call the undo_last_change
    tool and render its result", not "actually undo anything" (that is covered
    by the integration suite)."""

    def __init__(self, result: AgentToolResult) -> None:
        self._result = result

    async def execute(self, session, context, call, todos):
        return self._result


@pytest.mark.asyncio
async def test_run_undo_records_a_trace_so_eval_assertions_can_see_the_tool_call():
    """Regression test: run_undo used to skip self._trace.started(context), so
    TerminalTraceCollector never opened an active trace and tool_result()/
    completed() were no-ops -- eval_runner would see trace=None and any
    tool_required: undo_last_change assertion on a /undo turn would silently
    fail even though the tool actually executed."""
    from app.agent.journal_agent import JournalAgent

    traces = TerminalTraceCollector()
    tools = _StubTools(AgentToolResult.success({
        "changeSetId": uuid.uuid4(), "actions": 1,
        "undoneActions": [{"type": "CREATE", "description": "yogurt", "calories": 146}],
    }))
    agent = JournalAgent(model=None, tools=tools, max_tool_calls=1, trace=traces)
    context = _context(message="/undo")

    await agent.run_undo(session=None, context=context)

    trace = traces.await_trace()
    assert trace is not None
    assert [(t.name, t.outcome) for t in trace.tools] == [("undo_last_change", "OK")]
    assert trace.model_turns == 0  # /undo deliberately skips the model loop
    assert trace.reply_length > 0


@pytest.mark.asyncio
async def test_run_undo_records_a_trace_even_on_tool_failure():
    from app.agent.journal_agent import JournalAgent

    traces = TerminalTraceCollector()
    tools = _StubTools(AgentToolResult.failure("NOT_FOUND", "There is no recent journal change to undo."))
    agent = JournalAgent(model=None, tools=tools, max_tool_calls=1, trace=traces)
    context = _context(message="/undo")

    await agent.run_undo(session=None, context=context)

    trace = traces.await_trace()
    assert trace is not None
    assert [(t.name, t.outcome) for t in trace.tools] == [("undo_last_change", "NOT_FOUND")]


@pytest.mark.asyncio
async def test_run_undo_surfaces_agent_tool_failure_results_in_the_trace():
    from app.agent.journal_agent import JournalAgent

    traces = TerminalTraceCollector()

    class _FailingTools:
        async def execute(self, session, context, call, todos):
            raise AgentToolFailure(AgentToolResult.failure("NOT_FOUND", "nothing to undo"))

    agent = JournalAgent(model=None, tools=_FailingTools(), max_tool_calls=1, trace=traces)
    context = _context(message="/undo")

    await agent.run_undo(session=None, context=context)

    trace = traces.await_trace()
    assert trace is not None
    assert [(t.name, t.outcome) for t in trace.tools] == [("undo_last_change", "NOT_FOUND")]
