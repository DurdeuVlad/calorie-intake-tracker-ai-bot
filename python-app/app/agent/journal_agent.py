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

        calls = 0
        while True:
            try:
                reply = await self._model.next(context, recent, exchanges)
            except AgentProviderUnavailableError:
                logger.exception("Agent model call failed")
                return self._complete(self._fallback_receipt(exchanges) or self._unavailable())

            self._trace.model_reply(reply)
            if reply is None:
                return self._complete(self._fallback_receipt(exchanges) or self._unavailable())
            if not reply.tool_calls:
                if not reply.text or not reply.text.strip():
                    return self._complete(self._fallback_receipt(exchanges) or self._unavailable())
                return self._complete(self._safe_reply(reply.text))

            for call in reply.tool_calls:
                if calls >= self._max_calls:
                    return self._complete(self._fallback_receipt(exchanges) or self._limit())
                calls += 1

                try:
                    raw = await self._tools.execute(session, context, call, todos)
                except AgentToolFailure as failure:
                    raw = failure.result
                except Exception:
                    logger.exception("Tool execution failed: %s", call.name)
                    raise

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
            raise
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

    def _fallback_receipt(self, exchanges: list[AgentExchange]) -> str | None:
        """Render a minimal receipt when the model cannot finish its reply.

        This is deliberately limited to structured, already-committed journal
        results. It prevents a provider outage after a successful mutation from
        looking like the mutation never happened and causing a duplicate retry.
        """
        last_undo = -1
        for index, exchange in enumerate(exchanges):
            if exchange.call.name == "undo_last_change" and exchange.result.ok:
                last_undo = index

        batches: list[AgentToolResult] = []
        for exchange in exchanges[last_undo + 1:]:
            if exchange.call.name != "apply_journal_actions" or not exchange.result.ok:
                continue
            successful = exchange.result.data.get("successful")
            if isinstance(successful, int) and not isinstance(successful, bool) and successful > 0:
                batches.append(exchange.result)

        receipts: list[str] = []
        if last_undo >= 0:
            receipts.append(self._fallback_undo_receipt(exchanges[last_undo].result))

        if batches:
            lines: list[str] = []
            verbs = {"CREATE": "Logged", "EDIT": "Updated", "MOVE": "Moved", "DELETE": "Deleted"}
            undo_available = False
            for result in batches:
                data = result.data
                rows = data.get("results")
                if not isinstance(rows, list):
                    continue
                undo_available = undo_available or data.get("undoAvailable") is True
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    action_type = row.get("type") if isinstance(row.get("type"), str) else "Action"
                    if row.get("ok") is True:
                        entry = row.get("entry") if isinstance(row.get("entry"), dict) else {}
                        description = row.get("description") or entry.get("description") or "entry"
                        if not isinstance(description, str):
                            description = "entry"
                        description = " ".join(description.split())[:300] or "entry"
                        calories = row.get("calories")
                        suffix = f" — {calories} kcal" if isinstance(calories, int) and not isinstance(calories, bool) else ""
                        lines.append(f"{verbs.get(action_type, 'Changed')}: {description}{suffix}.")
                    else:
                        message = row.get("message")
                        if isinstance(message, str) and message:
                            message = " ".join(message.split())[:300]
                            lines.append(f"{action_type}: could not be applied ({message}).")
                        else:
                            lines.append(f"{action_type}: could not be applied.")
            if undo_available:
                if len(batches) == 1:
                    lines.append("Send Undo within 10 minutes to reverse the successful changes.")
                else:
                    lines.append("Send Undo within 10 minutes to reverse only the latest successful change batch.")
            if lines:
                receipts.append("\n".join(lines))

        durable_receipt = self._fallback_durable_tool_receipt(exchanges)
        if durable_receipt:
            receipts.append(durable_receipt)
        return self._safe_reply("\n".join(receipt for receipt in receipts if receipt)) if receipts else None

    def _fallback_durable_tool_receipt(self, exchanges: list[AgentExchange]) -> str | None:
        """Acknowledge durable non-journal tool work after a provider outage."""
        lines: list[str] = []
        for exchange in exchanges:
            if not exchange.result.ok:
                continue
            data = exchange.result.data
            if exchange.call.name == "search_packaged_food":
                products = data.get("products")
                if isinstance(products, list) and products:
                    lines.append(f"Found {len(products)} packaged nutrition choices. Reply with the one you want to use.")
            elif exchange.call.name == "estimate_food":
                item = data.get("item")
                if isinstance(item, dict):
                    name = item.get("name") if isinstance(item.get("name"), str) else "food"
                    calories = item.get("totalCalories")
                    suffix = f" — {calories} kcal" if isinstance(calories, int) and not isinstance(calories, bool) else ""
                    lines.append(f"Prepared an estimate for {' '.join(name.split())[:255]}{suffix}. Tell me if you want to log it.")
            elif exchange.call.name == "select_packaged_food":
                item = data.get("item")
                if isinstance(item, dict):
                    name = item.get("name") if isinstance(item.get("name"), str) else "the selected food"
                    lines.append(f"Selected {' '.join(name.split())[:255]}. Tell me if you want to log it.")
            elif exchange.call.name == "save_private_food":
                name = data.get("name")
                calories = data.get("caloriesPer100g")
                if isinstance(name, str):
                    suffix = f" ({calories} kcal/100 g)" if isinstance(calories, int) and not isinstance(calories, bool) else ""
                    lines.append(f"Saved household food: {' '.join(name.split())[:255]}{suffix}.")
            elif exchange.call.name == "save_alias":
                message = data.get("message")
                if isinstance(message, str) and message.strip():
                    lines.append(" ".join(message.split())[:300])
            elif exchange.call.name == "update_settings" and data.get("updated") is True:
                lines.append("Updated your settings.")
        return self._safe_reply("\n".join(lines)) if lines else None

    def _fallback_undo_receipt(self, result: AgentToolResult) -> str:
        undone = result.data.get("undoneActions")
        if not isinstance(undone, list):
            return self._safe_reply("Undid the latest journal change.")
        items: list[str] = []
        for action in undone:
            if not isinstance(action, dict):
                continue
            description = action.get("description")
            if not isinstance(description, str):
                description = "entry"
            description = " ".join(description.split())[:300] or "entry"
            calories = action.get("calories")
            suffix = f" ({calories} kcal)" if isinstance(calories, int) and not isinstance(calories, bool) else ""
            items.append(f"{description}{suffix}")
        return self._safe_reply(f"Undid: {', '.join(items)}" if items else "Undid the latest journal change.")

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
