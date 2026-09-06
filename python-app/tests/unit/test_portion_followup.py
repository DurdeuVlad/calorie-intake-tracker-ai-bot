"""Regression tests for estimate_followup_context and the conversational
guard in journal_tool_executor.

These cover the v2.0 evaluation failures:
- memory-does-not-hijack: "mulțumesc" must not be rewritten into a logging
  instruction even when the previous assistant turn asked a portion question.
- Single-food auto-estimate: "am avut paste cu chicken" (no calories, no
  combo) gets a server-injected estimate hint so the model logs immediately.
- Combo exclusion: combo meals are NOT auto-estimated; the model should ask
  once per the combos instructions.
- Conversational guard: apply_journal_actions is blocked deterministically
  on purely conversational messages.
"""

from app.agent.portion_followup import (
    _is_conversational_reply,
    _is_food_intake_without_calories,
    estimate_followup_context,
)
from app.db.models.conversation import ConversationMemory
from app.domain.agent_types import AgentContext
from app.services.journal_tool_executor import _is_conversational_message


def _ctx(message: str) -> AgentContext:
    return AgentContext(user=None, chat_id="1", message=message)  # type: ignore[arg-type]


def test_mulțumesc_is_conversational():
    assert _is_conversational_reply("mulțumesc")
    assert _is_conversational_reply("Mulțumesc!")
    assert _is_conversational_reply("mersi")
    assert _is_conversational_reply("thanks")
    assert _is_conversational_reply("ok")


def test_food_message_is_not_conversational():
    assert not _is_conversational_reply("am mancat pui")
    assert not _is_conversational_reply("200 g crispy")


def test_food_intake_without_calories_detected():
    assert _is_food_intake_without_calories("am avut paste cu chicken")
    assert _is_food_intake_without_calories("am mancat pui")
    assert _is_food_intake_without_calories("I had pasta")


def test_food_with_calories_not_auto_estimated():
    assert not _is_food_intake_without_calories("am mancat pui 300 kcal")
    assert not _is_food_intake_without_calories("200 g crispy, 229 kcal/100 g")


def test_combo_meal_not_auto_estimated():
    assert not _is_food_intake_without_calories(
        "Am mancat un meniu de burger cu cartofi si o bautura, nu stiu exact cat"
    )
    assert not _is_food_intake_without_calories(
        "Am mancat de la taco bell asa: un taco cu vita moale, si un meniu cu burrito mare"
    )


def test_estimate_followup_does_not_rewrite_mulțumesc():
    """The critical regression: 'mulțumesc' after a portion question must not
    be rewritten into 'Estimate this meal now: ...'."""
    recent = [
        ConversationMemory(role="user", content="am avut paste cu chicken"),
        ConversationMemory(role="assistant", content="Câte calorii au avut pastele cu pui?"),
    ]
    result = estimate_followup_context(_ctx("mulțumesc"), recent)
    assert result.message == "mulțumesc"


def test_estimate_followup_rewrites_decline():
    """A genuine decline like 'nu stiu' should trigger the estimate rewrite."""
    recent = [
        ConversationMemory(role="user", content="am avut paste cu chicken"),
        ConversationMemory(role="assistant", content="Câte calorii au avut pastele cu pui?"),
    ]
    result = estimate_followup_context(_ctx("nu stiu"), recent)
    assert result.message == "Estimate this meal now: am avut paste cu chicken"


def test_estimate_followup_rewrites_scrie_tu():
    """'Scrie tu' is an explicit estimate request."""
    recent = [
        ConversationMemory(role="user", content="Am mancat un meniu de burger cu cartofi"),
        ConversationMemory(role="assistant", content="Câte calorii aproximativ?"),
    ]
    result = estimate_followup_context(_ctx("Scrie tu, conteaza doar caloriile"), recent)
    assert result.message == "Estimate this meal now: Am mancat un meniu de burger cu cartofi"


def test_first_turn_food_intake_gets_estimate_hint():
    """Single food without calories on the first turn gets an estimate hint."""
    result = estimate_followup_context(_ctx("am avut paste cu chicken"), [])
    assert "estimate and log" in result.message.lower()
    assert "am avut paste cu chicken" in result.message


def test_first_turn_combo_does_not_get_estimate_hint():
    """Combo meals on the first turn do NOT get an auto-estimate hint."""
    result = estimate_followup_context(
        _ctx("Am mancat un meniu de burger cu cartofi si o bautura, nu stiu exact cat"), []
    )
    assert result.message == "Am mancat un meniu de burger cu cartofi si o bautura, nu stiu exact cat"


def test_conversational_message_guard_blocks_apply_journal_actions():
    """The deterministic guard in journal_tool_executor must recognize
    conversational messages that would trigger apply_journal_actions."""
    assert _is_conversational_message("mulțumesc")
    assert _is_conversational_message("mersi")
    assert _is_conversational_message("thanks")
    assert _is_conversational_message("ok")
    assert _is_conversational_message("salut")


def test_non_conversational_message_passes_guard():
    assert not _is_conversational_message("am mancat pui")
    assert not _is_conversational_message("200 g crispy, 700 kcal pe ieri")
    assert not _is_conversational_message("mută salata de azi pe ieri")
    assert not _is_conversational_message("cate calorii are un Big Mac?")
