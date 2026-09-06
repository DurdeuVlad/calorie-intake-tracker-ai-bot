"""The bounded ReAct tool loop. The model is
never given repositories or provider credentials -- it can only call typed
tools through JournalToolExecutor.

v2.0: The model writes full replies from structured tool results. No
deterministic reply templates, no `if context.romanian` branches. The
system prompt instructs the model on receipt format and language."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.openai_model_client import (
    AgentProviderUnavailableError,
    OpenAiJournalAgentModel,
)
from app.agent.portion_followup import estimate_followup_context
from app.agent.trace_sink import AgentTraceSink, NoopTraceSink
from app.db.models.conversation import ConversationMemory
from app.domain.agent_types import (
    AgentContext,
    AgentExchange,
    AgentToolFailure,
    AgentToolResult,
    ToolCall,
)
from app.services.journal_tool_executor import JournalToolExecutor

logger = logging.getLogger(__name__)


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
                return self._complete(self._unavailable())

            self._trace.model_reply(reply)
            if reply is None:
                return self._complete(self._unavailable())
            if not reply.tool_calls:
                return self._complete(self._safe_reply(reply.text))

            for call in reply.tool_calls:
                if calls >= self._max_calls:
                    return self._complete(self._limit())
                calls += 1

                try:
                    raw = await self._tools.execute(session, active, call, todos)
                except AgentToolFailure as failure:
                    raw = failure.result
                except Exception:
                    logger.exception("Tool execution failed: %s", call.name)
                    raw = AgentToolResult.failure("TEMPORARY_FAILURE", "That operation could not be completed now.")

                data: dict[str, Any] = {**raw.data, "todos": list(todos)}
                result = AgentToolResult(raw.ok, raw.code, data, raw.user_hint)
                exchanges.append(AgentExchange(call, result))
                self._trace.tool_result(call, result)

                # v2.0: no deterministic reply rendering. The model writes the
                # full reply from the structured tool result on the next turn.
                # For apply_journal_actions with at least one success, the
                # system prompt tells the model to write a receipt and NOT
                # retry (successful actions are already committed). For an
                # all-failure batch, the model may retry with corrected args.
                # The loop continues to the next model turn in all cases.

    async def run_undo(self, session: AsyncSession, context: AgentContext) -> str:
        """Deterministic entry point for the /undo slash command. Invokes the
        same undo_last_change tool the agent calls for natural-language undo
        ("undo that", "anuleaza"), without spending a model turn -- undo must
        stay instant and free even though the slash-command dispatch table in
        journal_application_service.py does not go through the model loop."""
        self._trace.started(context)
        call = ToolCall(id="slash-undo", name="undo_last_change", arguments="{}")
        try:
            result = await self._tools.execute(session, context, call, [])
        except AgentToolFailure as failure:
            result = failure.result
        except Exception:
            logger.exception("Tool execution failed: %s", call.name)
            result = AgentToolResult.failure("TEMPORARY_FAILURE", "That operation could not be completed now.")
        self._trace.tool_result(call, result)
        if result.ok:
            undone = result.data.get("undoneActions") or []
            if undone:
                items = ", ".join(
                    f"{a.get('description', 'entry')} ({a.get('calories', '?')} kcal)"
                    for a in undone if isinstance(a, dict)
                )
                return self._complete(f"Undid: {items}" if items else "Undid the latest journal change.")
            return self._complete("Undid the latest journal change.")
        return self._complete(result.user_hint or "That could not be undone right now.")

    def _complete(self, reply: str) -> str:
        self._trace.completed(reply)
        return reply

    def _safe_reply(self, text: str | None) -> str:
        if not text or not text.strip():
            return self._unavailable()
        return text if len(text) <= 3500 else text[:3500]

    def _unavailable(self) -> str:
        return "I cannot process that right now. Please try again or send the meal details as text."

    def _limit(self) -> str:
        return "I need one more detail to finish safely. Tell me the food, quantity, or journal entry involved."
