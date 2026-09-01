import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.agent.journal_agent import JournalAgent
from app.db.models.nutrition import NutritionEvidence
from app.domain.agent_types import (
    AgentContext,
    AgentToolFailure,
    AgentToolResult,
    ToolCall,
)
from app.terminal.trace_collector import TerminalTraceCollector


def _agent() -> JournalAgent:
    return JournalAgent(model=None, tools=None, max_tool_calls=1)


def _context(**kwargs) -> AgentContext:
    defaults = {"user": None, "chat_id": "1", "romanian": False, "message": "meal"}
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


def test_verified_receipt_shows_auditable_source_and_derivation():
    lines = _agent()._meal_receipt(_context(), {"description": "yogurt", "calories": 146}, {}, _evidence())

    reply = "\n".join(lines)
    assert reply == (
        "Logged: yogurt — 146 kcal\n"
        "Food: Greek yogurt Acme; 150 g × 97 kcal/100 g = 146 kcal.\n"
        "Verified source: Open Food Facts (fetched from provider); confidence: high.\n"
        "Source: https://world.openfoodfacts.org/product/123"
    )


@pytest.mark.asyncio
async def test_canonical_success_reply_is_a_receipt_with_undo(monkeypatch):
    evidence = _evidence()

    async def find_evidence(session, entry_ids):
        return {1: evidence}

    monkeypatch.setattr("app.agent.journal_agent.nutrition_evidence_repo.find_by_food_entry_ids", find_evidence)
    reply = await _agent()._canonical_reply(
        None,
        _context(),
        ToolCall("1", "apply_journal_actions", "{}"),
        AgentToolResult.success({
            "results": [{"ok": True, "type": "CREATE", "entry": {"id": 1, "description": "yogurt", "calories": 146}}],
            "undoAvailable": True,
        }),
    )

    assert reply == (
        "Logged: yogurt — 146 kcal\n"
        "Food: Greek yogurt Acme; 150 g × 97 kcal/100 g = 146 kcal.\n"
        "Verified source: Open Food Facts (fetched from provider); confidence: high.\n"
        "Source: https://world.openfoodfacts.org/product/123\n"
        "Send Undo within 10 minutes to reverse the successful changes."
    )


def test_cached_and_stale_receipts_do_not_claim_a_live_lookup():
    recent = _agent()._meal_receipt(
        _context(), {"description": "yogurt", "calories": 146}, {}, _evidence(source_cache_hit=True)
    )
    stale = _agent()._meal_receipt(
        _context(), {"description": "yogurt", "calories": 146}, {},
        _evidence(source_cache_hit=True, source_fetched_at=datetime.now(UTC) - timedelta(days=31)),
    )

    assert "cached; not a live lookup" in "\n".join(recent)
    assert "cached/stale; not a live lookup" in "\n".join(stale)


def test_manual_and_estimate_receipts_are_not_presented_as_verified():
    manual = _agent()._meal_receipt(
        _context(), {"description": "toast", "calories": 120}, {"nutritionSource": "manual", "nutritionConfidence": "high"}, None
    )
    estimate = _agent()._meal_receipt(
        _context(), {"description": "curry", "calories": 500}, {"nutritionSource": "ai_estimate", "nutritionConfidence": "estimate"}, None
    )

    assert "Source: manual value; confidence: high." in "\n".join(manual)
    assert "Source: unverified value; confidence: estimate." in "\n".join(estimate)
    assert "Verified source" not in "\n".join(manual + estimate)


def test_manual_explicit_calories_explain_the_user_provided_basis_and_serving():
    lines = _agent()._meal_receipt(
        _context(),
        {"description": "toast", "calories": 120},
        {"nutritionSource": "manual", "nutritionConfidence": "high", "receipt": {"quantity": 2, "unit": "portion"}},
        None,
    )

    assert lines[-1] == "Basis: user-provided 120 kcal for 2 portion."


def test_ai_estimate_explains_its_server_basis_without_claiming_a_url():
    lines = _agent()._meal_receipt(
        _context(),
        {"description": "curry", "calories": 500},
        {"nutritionSource": "ai_estimate", "nutritionConfidence": "estimate", "receipt": {"basis": "visible bowl portion"}},
        None,
    )

    reply = "\n".join(lines)
    assert "Estimate recorded; no verified source or URL is available. Basis: visible bowl portion." in reply
    assert "Source: AI estimate; confidence: estimate." in reply


def test_private_and_unknown_receipts_explain_when_no_calculation_is_available():
    private = _agent()._meal_receipt(
        _context(), {"description": "family soup", "calories": 250},
        {"nutritionSource": "private", "nutritionConfidence": "unknown", "receipt": {"basis": "private food value"}}, None,
    )
    unknown = _agent()._meal_receipt(
        _context(), {"description": "snack", "calories": 180},
        {"nutritionSource": "mixed", "nutritionConfidence": "unknown"}, None,
    )

    assert "private food value" not in "\n".join(private).lower()
    assert private[-1] == "No verified source calculation is available. Send a correction with the food, serving, or calories if this is wrong."
    assert unknown[-1] == "No verified source calculation is available. Send a correction with the food, serving, or calories if this is wrong."


def test_forged_source_label_is_rendered_as_unverified_manual_value():
    lines = _agent()._meal_receipt(
        _context(),
        {"description": "family soup", "calories": 250},
        {
            "nutritionSource": "manual",
            "nutritionConfidence": "unknown",
            "receipt": {"basis": "unverified source label ignored; no confirmed source for this calorie value"},
        },
        None,
    )

    reply = "\n".join(lines)
    assert "private" not in reply.lower()
    assert "Source: manual value; confidence: unknown." in reply
    assert "Basis: unverified source label ignored; no confirmed source for this calorie value." in reply


def test_non_evidence_per_100g_result_gets_a_deterministic_formula():
    lines = _agent()._meal_receipt(
        _context(), {"description": "estimated curry", "calories": 500},
        {"nutritionSource": "ai_estimate", "nutritionConfidence": "estimate", "receipt": {"quantity": 250, "unit": "g", "caloriesPer100g": 200}},
        None,
    )

    assert lines[-1] == "Calculation: 250 g × 200 kcal/100 g = 500 kcal."


def test_voice_receipt_quotes_the_server_transcript_and_offers_undo_elsewhere():
    lines = _agent()._media_lines(_context(media_kind="voice", media_text="two eggs and toast"))

    assert lines == ["I heard: two eggs and toast"]


def test_photo_receipt_surfaces_the_material_question():
    lines = _agent()._media_lines(_context(
        media_kind="photo",
        media_text="Interpretation: rice bowl with chicken\nEstimate: portion unclear\nConfidence: low; no scale\nQuestion: Was this one or two servings?",
    ))

    assert lines == [
        "Photo: rice bowl with chicken",
        "Estimate: portion unclear; confidence: low; no scale.",
        "Question: Was this one or two servings?",
    ]


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
    traces = TerminalTraceCollector()
    tools = _StubTools(AgentToolResult.success({"changeSetId": uuid.uuid4(), "actions": 1}))
    agent = JournalAgent(model=None, tools=tools, max_tool_calls=1, trace=traces)
    context = _context(message="/undo")

    await agent.run_undo(session=None, context=context)

    trace = traces.await_trace()
    assert trace is not None
    assert [(t.name, t.outcome) for t in trace.tools] == [("undo_last_change", "OK")]
    assert trace.model_turns == 0  # /undo deliberately skips the model loop
    assert trace.reply_length == len("Undid the latest journal change.")


@pytest.mark.asyncio
async def test_run_undo_records_a_trace_even_on_tool_failure():
    """The trace must be recorded regardless of tool outcome, so eval
    assertions like tool_outcome: undo_last_change:NOT_FOUND still work."""
    traces = TerminalTraceCollector()
    tools = _StubTools(AgentToolResult.failure("NOT_FOUND", "There is no recent journal change to undo."))
    agent = JournalAgent(model=None, tools=tools, max_tool_calls=1, trace=traces)
    context = _context(message="/undo", romanian=False)

    await agent.run_undo(session=None, context=context)

    trace = traces.await_trace()
    assert trace is not None
    assert [(t.name, t.outcome) for t in trace.tools] == [("undo_last_change", "NOT_FOUND")]


@pytest.mark.asyncio
async def test_run_undo_surfaces_agent_tool_failure_results_in_the_trace():
    """AgentToolFailure is the short-circuit path the real tool executor uses
    for NOT_FOUND/VALIDATION_ERROR; run_undo must unwrap it the same way run()
    does, and the trace must reflect the unwrapped code, not the exception."""
    traces = TerminalTraceCollector()

    class _FailingTools:
        async def execute(self, session, context, call, todos):
            raise AgentToolFailure(AgentToolResult.failure("NOT_FOUND", "nothing to undo"))

    agent = JournalAgent(model=None, tools=_FailingTools(), max_tool_calls=1, trace=traces)
    context = _context(message="/undo", romanian=False)

    await agent.run_undo(session=None, context=context)

    trace = traces.await_trace()
    assert trace is not None
    assert [(t.name, t.outcome) for t in trace.tools] == [("undo_last_change", "NOT_FOUND")]
