"""Ported verbatim from JournalAgent.estimateFollowupContext()/looksLikePortionQuestion().
`recent` is chronologically ascending (oldest first), matching
ConversationMemoryService.recent()."""

from dataclasses import replace

from app.db.models.conversation import ConversationMemory
from app.domain.agent_types import AgentContext

_DECLINE_KEYWORDS = ("nu știu", "nu stiu", "estimează", "estimeaza", "i don't know", "estimate it")


def _looks_like_portion_question(text: str | None) -> bool:
    value = (text or "").lower()
    return any(token in value for token in ("gram", "quantity", "cantitate", "cât", "cat "))


def estimate_followup_context(context: AgentContext, recent: list[ConversationMemory]) -> AgentContext:
    reply = (context.message or "").strip().lower()
    if not recent:
        return context
    previous_assistant = recent[-1]
    if previous_assistant.role != "assistant" or not _looks_like_portion_question(previous_assistant.content):
        return context

    declined_by_keyword = any(keyword in reply for keyword in _DECLINE_KEYWORDS)
    declined_by_no_digits = bool(reply) and not any(ch.isdigit() for ch in reply)
    if not declined_by_keyword and not declined_by_no_digits:
        return context

    for turn in reversed(recent[:-1]):
        if turn.role == "user":
            return replace(context, message=f"Estimate this meal now: {turn.content}")
    return context
