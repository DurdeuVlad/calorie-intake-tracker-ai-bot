"""Ported verbatim from JournalAgent.estimateFollowupContext()/looksLikePortionQuestion().
`recent` is chronologically ascending (oldest first), matching
ConversationMemoryService.recent()."""

import re
from dataclasses import replace

from app.db.models.conversation import ConversationMemory
from app.domain.agent_types import AgentContext

_DECLINE_KEYWORDS = ("nu știu", "nu stiu", "estimează", "estimeaza", "i don't know", "estimate it", "estimate", "tu știi", "tu stii", "nu conteaza", "nu contează", "scrie tu")

# Purely conversational replies that must never be interpreted as a portion
# decline/estimate request. These are greetings, thanks, and bare acks.
_CONVERSATIONAL_KEYWORDS = (
    "mulțumesc", "multumesc", "mersi", "thanks", "thank you", "thx",
    "ok", "bine", "great", "super", "perfect", "da", "yes", "yeah",
    "salut", "hi", "hello", "hey", "servus", "buna", "bună",
    "ceau", "pa", "la revedere", "bye", "gata", "cool", "nice",
    "no problem", "np", "foarte bine", "excelent", "de acord", "agree",
)

# Patterns that indicate the user is reporting food they ate, without giving
# calories or a quantity with calories. The model should estimate and log
# immediately rather than asking for more info.
_FOOD_INTAKE_RE = re.compile(
    r"\b(?:am\s+(?:mâncat|mancat|avut|mancat)|i\s+(?:ate|had)|mi-am\s+luat|am\s+luat)\b",
    re.IGNORECASE,
)
# If the message already contains explicit calories, don't inject the hint.
_CALORIES_RE = re.compile(r"\b\d{2,5}\s*(?:kcal|calorii|calories)\b", re.IGNORECASE)
# Combo meal indicators — multiple items ordered together. These should NOT
# trigger auto-estimate; the model should ask once for a total or breakdown.
_COMBO_INDICATORS = ("meniu", "combo", "meniul", "un meniu", "un taco", "burrito", "cartofi pai", "sos nacho", "burger cu cartofi", "bautura", "băutură")


def _looks_like_portion_question(text: str | None) -> bool:
    value = (text or "").lower()
    return any(token in value for token in ("gram", "quantity", "cantitate", "cât", "cat ", "calorii", "porț", "portie", "porție"))


def _is_conversational_reply(reply: str) -> bool:
    stripped = reply.strip().lower()
    if not stripped:
        return True
    for keyword in _CONVERSATIONAL_KEYWORDS:
        if stripped == keyword or stripped == keyword + "." or stripped == keyword + "!" or stripped == keyword + "?":
            return True
    return False


def _is_food_intake_without_calories(message: str) -> bool:
    """True when the user reports eating a single food without calories.
    Combo meals (multiple items, "meniu") are excluded — the model should
    ask once for those per the combos instructions."""
    if not message:
        return False
    if _CALORIES_RE.search(message):
        return False
    if not _FOOD_INTAKE_RE.search(message):
        return False
    lower = message.lower()
    return not any(indicator in lower for indicator in _COMBO_INDICATORS)


def estimate_followup_context(context: AgentContext, recent: list[ConversationMemory]) -> AgentContext:
    reply = (context.message or "").strip().lower()

    # Deterministic: if the user says they ate a food without calories, inject
    # an explicit estimate instruction so the model doesn't ask the user for
    # nutrition data they don't have. This is a business rule, not a prompt
    # suggestion — the model must estimate and log, not quiz the user.
    if not recent and _is_food_intake_without_calories(context.message or ""):
        return replace(context, message=f"[Server note: estimate and log this meal now — do not ask the user for calories or portion.]\n{context.message}")

    if not recent:
        return context
    previous_assistant = recent[-1]
    if previous_assistant.role != "assistant" or not _looks_like_portion_question(previous_assistant.content):
        return context

    # A purely conversational reply (thanks, greeting, bare ack) is NOT a
    # decline or estimate request — it is a conversation turn that must not
    # be rewritten into a food-logging instruction.
    if _is_conversational_reply(reply):
        return context

    declined_by_keyword = any(keyword in reply for keyword in _DECLINE_KEYWORDS)
    declined_by_no_digits = bool(reply) and not any(ch.isdigit() for ch in reply)
    if not declined_by_keyword and not declined_by_no_digits:
        return context

    for turn in reversed(recent[:-1]):
        if turn.role == "user":
            return replace(context, message=f"Estimate this meal now: {turn.content}")
    return context
