"""Regression tests for estimate_followup_context.

The v2.0 agent previously rewrote the user's message before sending it to the
model. That was wrong — the model must see exactly what the user sent. These
tests verify that estimate_followup_context is now a no-op passthrough: it
never alters, replaces, or augments the user's message, regardless of
conversation history or message content.
"""

from app.agent.portion_followup import estimate_followup_context
from app.db.models.conversation import ConversationMemory
from app.domain.agent_types import AgentContext


def _ctx(message: str) -> AgentContext:
    return AgentContext(user=None, chat_id="1", message=message)  # type: ignore[arg-type]


def test_passthrough_no_history():
    """No conversation history — message passes through unchanged."""
    assert estimate_followup_context(_ctx("am avut paste cu chicken"), []).message == "am avut paste cu chicken"


def test_passthrough_mulțumesc_after_portion_question():
    """The critical regression: 'mulțumesc' after a portion question must
    pass through unchanged. The model sees 'mulțumesc', not a fabricated
    logging instruction."""
    recent = [
        ConversationMemory(role="user", content="am avut paste cu chicken"),
        ConversationMemory(role="assistant", content="Câte calorii au avut pastele cu pui?"),
    ]
    assert estimate_followup_context(_ctx("mulțumesc"), recent).message == "mulțumesc"


def test_passthrough_decline_after_portion_question():
    """A genuine decline like 'nu stiu' also passes through unchanged.
    The model is trusted to interpret it from conversation context."""
    recent = [
        ConversationMemory(role="user", content="am avut paste cu chicken"),
        ConversationMemory(role="assistant", content="Câte calorii au avut pastele cu pui?"),
    ]
    assert estimate_followup_context(_ctx("nu stiu"), recent).message == "nu stiu"


def test_passthrough_scrie_tu():
    """'Scrie tu' passes through unchanged."""
    recent = [
        ConversationMemory(role="user", content="Am mancat un meniu de burger cu cartofi"),
        ConversationMemory(role="assistant", content="Câte calorii aproximativ?"),
    ]
    assert estimate_followup_context(_ctx("Scrie tu, conteaza doar caloriile"), recent).message == "Scrie tu, conteaza doar caloriile"


def test_passthrough_combo_first_turn():
    """Combo meal on first turn passes through unchanged."""
    msg = "Am mancat un meniu de burger cu cartofi si o bautura, nu stiu exact cat"
    assert estimate_followup_context(_ctx(msg), []).message == msg


def test_passthrough_food_with_calories():
    """Food with explicit calories passes through unchanged."""
    assert estimate_followup_context(_ctx("am mancat pui 300 kcal"), []).message == "am mancat pui 300 kcal"


def test_passthrough_empty_message():
    """Empty message passes through unchanged."""
    assert estimate_followup_context(_ctx(""), []).message == ""


def test_passthrough_greeting():
    """A greeting passes through unchanged."""
    assert estimate_followup_context(_ctx("salut"), []).message == "salut"
