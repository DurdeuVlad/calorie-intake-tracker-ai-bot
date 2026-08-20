"""The bounded ReAct tool loop, ported from JournalAgent.java. The model is
never given repositories or provider credentials -- it can only call typed
tools through JournalToolExecutor.

Note: the `create_food_entry` legacy tool's canonical-reply branch from the
Java source is intentionally dropped here (see journal_tool_executor.py's
module docstring for why)."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.openai_model_client import AgentProviderUnavailableError, OpenAiJournalAgentModel
from app.agent.portion_followup import estimate_followup_context
from app.agent.trace_sink import AgentTraceSink, NoopTraceSink
from app.db.models.conversation import ConversationMemory
from app.domain.agent_types import AgentContext, AgentExchange, AgentToolFailure, AgentToolResult, ToolCall
from app.services.journal_tool_executor import JournalToolExecutor

logger = logging.getLogger(__name__)

_VERBS = {
    "CREATE": ("Notat", "Logged"),
    "EDIT": ("Modificat", "Updated"),
    "MOVE": ("Mutat", "Moved"),
    "DELETE": ("Șters", "Deleted"),
}


class JournalAgent:
    def __init__(
        self,
        model: OpenAiJournalAgentModel,
        tools: JournalToolExecutor,
        max_tool_calls: int,
        memory_recent=None,
        trace: AgentTraceSink | None = None,
    ) -> None:
        self._model = model
        self._tools = tools
        self._max_calls = max_tool_calls
        self._memory_recent = memory_recent  # async (session, user) -> list[ConversationMemory], or None
        self._trace = trace or NoopTraceSink()

    async def run(self, session: AsyncSession, context: AgentContext) -> str:
        self._trace.started(context)
        exchanges: list[AgentExchange] = []
        todos: list[str] = []
        recent: list[ConversationMemory] = await self._memory_recent(session, context.user) if self._memory_recent else []
        active = estimate_followup_context(context, recent)

        calls = 0
        while True:
            try:
                reply = await self._model.next(active, recent, exchanges)
            except AgentProviderUnavailableError:
                logger.exception("Agent model call failed")
                return self._complete(self._unavailable(active))

            self._trace.model_reply(reply)
            if reply is None:
                return self._complete(self._unavailable(active))
            if not reply.tool_calls:
                return self._complete(self._safe_reply(reply.text, active))

            for call in reply.tool_calls:
                if calls >= self._max_calls:
                    return self._complete(self._limit(active))
                calls += 1

                try:
                    raw = await self._tools.execute(session, active, call, todos)
                except AgentToolFailure as failure:
                    raw = failure.result
                except Exception:  # noqa: BLE001
                    logger.exception("Tool execution failed: %s", call.name)
                    raw = AgentToolResult.failure("TEMPORARY_FAILURE", "That operation could not be completed now.")

                data: dict[str, Any] = {**raw.data, "todos": list(todos)}
                result = AgentToolResult(raw.ok, raw.code, data, raw.user_hint)
                exchanges.append(AgentExchange(call, result))
                self._trace.tool_result(call, result)

                rendered = self._canonical_reply(active, call, result)
                if rendered is not None:
                    return self._complete(rendered)

    def _complete(self, reply: str) -> str:
        self._trace.completed(reply)
        return reply

    def _safe_reply(self, text: str | None, context: AgentContext) -> str:
        if not text or not text.strip():
            return self._unavailable(context)
        return text if len(text) <= 3500 else text[:3500]

    def _canonical_reply(self, context: AgentContext, call: ToolCall, result: AgentToolResult) -> str | None:
        if call.name == "apply_journal_actions" and result.ok:
            rows = result.data.get("results") or []
            rows = [r for r in rows if isinstance(r, dict)]
            if not rows:
                return "Nu am putut aplica nicio schimbare." if context.romanian else "No journal changes could be applied."

            lines: list[str] = []
            for row in rows:
                ok = row.get("ok") is True
                action_type = str(row.get("type", "ACTION"))
                if not ok:
                    fallback = "Schimbarea a eșuat." if context.romanian else "The change failed."
                    lines.append(f"- {row.get('message', fallback)}")
                    continue
                entry = row.get("entry") or {}
                description = str(entry.get("description", "entry"))
                calories = str(entry.get("calories", "?"))
                date = str(row.get("date", entry.get("date", "")))
                verb_ro, verb_en = _VERBS.get(action_type, ("Aplicat", "Applied"))
                verb = verb_ro if context.romanian else verb_en
                suffix_date = f" ({date})" if date else ""
                lines.append(f"- {verb}: {description} — {calories} kcal{suffix_date}")

            undoable = result.data.get("undoAvailable") is True
            if undoable:
                suffix = (
                    "\nScrie Undo în următoarele 10 minute pentru a anula schimbările reușite."
                    if context.romanian
                    else "\nSend Undo within 10 minutes to reverse the successful changes."
                )
            else:
                suffix = ""
            return "\n".join(lines) + suffix

        if call.name == "undo_last_change" and result.ok:
            return "Am anulat ultima schimbare din jurnal." if context.romanian else "Undid the latest journal change."

        return None

    def _unavailable(self, context: AgentContext) -> str:
        return (
            "Nu pot procesa cererea acum. Încearcă din nou sau trimite detaliile mesei în text."
            if context.romanian
            else "I cannot process that right now. Please try again or send the meal details as text."
        )

    def _limit(self, context: AgentContext) -> str:
        return (
            "Am nevoie de un detaliu în plus ca să termin în siguranță. Spune exact alimentul, cantitatea sau intrarea vizată."
            if context.romanian
            else "I need one more detail to finish safely. Tell me the food, quantity, or journal entry involved."
        )
