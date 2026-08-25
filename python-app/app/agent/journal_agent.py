"""The bounded ReAct tool loop, ported from JournalAgent.java. The model is
never given repositories or provider credentials -- it can only call typed
tools through JournalToolExecutor.

Note: the `create_food_entry` legacy tool's canonical-reply branch from the
Java source is intentionally dropped here (see journal_tool_executor.py's
module docstring for why)."""

import json
import logging
from datetime import UTC, datetime, timedelta
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
from app.repositories import nutrition_evidence_repo
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
                except Exception:
                    logger.exception("Tool execution failed: %s", call.name)
                    raw = AgentToolResult.failure("TEMPORARY_FAILURE", "That operation could not be completed now.")

                data: dict[str, Any] = {**raw.data, "todos": list(todos)}
                result = AgentToolResult(raw.ok, raw.code, data, raw.user_hint)
                exchanges.append(AgentExchange(call, result))
                self._trace.tool_result(call, result)

                rendered = await self._canonical_reply(session, active, call, result)
                if rendered is not None:
                    return self._complete(rendered)

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
            return self._complete("Am anulat ultima schimbare din jurnal." if context.romanian else "Undid the latest journal change.")
        fallback = "Nu am putut anula schimbarea." if context.romanian else "That could not be undone right now."
        return self._complete(result.user_hint or fallback)

    def _complete(self, reply: str) -> str:
        self._trace.completed(reply)
        return reply

    def _safe_reply(self, text: str | None, context: AgentContext) -> str:
        if not text or not text.strip():
            return self._unavailable(context)
        return text if len(text) <= 3500 else text[:3500]

    async def _canonical_reply(self, session: AsyncSession, context: AgentContext, call: ToolCall, result: AgentToolResult) -> str | None:
        if call.name == "apply_journal_actions" and result.ok:
            rows = result.data.get("results") or []
            rows = [r for r in rows if isinstance(r, dict)]
            if not rows:
                return "Nu am putut aplica nicio schimbare." if context.romanian else "No journal changes could be applied."

            created_ids = [
                row.get("entry", {}).get("id")
                for row in rows
                if row.get("ok") is True and str(row.get("type", "")).upper() == "CREATE" and isinstance(row.get("entry"), dict)
            ]
            evidence_by_entry = await nutrition_evidence_repo.find_by_food_entry_ids(
                session, [entry_id for entry_id in created_ids if isinstance(entry_id, int)]
            )

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
                if action_type == "CREATE":
                    lines.extend(self._meal_receipt(context, entry, row, evidence_by_entry.get(entry.get("id"))))
                    continue
                verb_ro, verb_en = _VERBS.get(action_type, ("Aplicat", "Applied"))
                verb = verb_ro if context.romanian else verb_en
                suffix_date = f" ({date})" if date else ""
                lines.append(f"- {verb}: {description} — {calories} kcal{suffix_date}")

            undoable = result.data.get("undoAvailable") is True
            media_lines = self._media_lines(context)
            if undoable:
                suffix = (
                    "\nScrie Undo în următoarele 10 minute pentru a anula schimbările reușite."
                    if context.romanian
                    else "\nSend Undo within 10 minutes to reverse the successful changes."
                )
            else:
                suffix = ""
            return "\n".join([*media_lines, *lines]) + suffix

        if call.name == "undo_last_change" and result.ok:
            return "Am anulat ultima schimbare din jurnal." if context.romanian else "Undid the latest journal change."

        return None

    def _meal_receipt(self, context: AgentContext, entry: dict[str, Any], row: dict[str, Any], evidence) -> list[str]:
        """Render server-owned provenance as a short, Telegram-safe receipt."""
        description = self._clean(entry.get("description", "meal"), 180)
        calories = entry.get("calories", "?")
        if evidence is None:
            source = str(row.get("nutritionSource") or "manual")
            confidence = str(row.get("nutritionConfidence") or "unknown")
            receipt = row.get("receipt") if isinstance(row.get("receipt"), dict) else {}
            trusted_ai_estimate = source == "ai_estimate" and (
                receipt.get("caloriesPer100g") is not None or bool(receipt.get("basis"))
            )
            source_label = {
                "manual": "manual value",
                "mixed": "mixed estimate",
                "open_food_facts_estimate": "Open Food Facts-based estimate",
            }.get(source, "AI estimate" if trusted_ai_estimate else "unverified value")
            lines = [
                f"Logged: {description} — {calories} kcal",
                f"Source: {source_label}; confidence: {confidence}.",
            ]
            quantity = receipt.get("quantity")
            unit = self._clean(receipt.get("unit"), 16)
            per_100g = receipt.get("caloriesPer100g")
            if unit == "g" and quantity is not None and per_100g is not None:
                lines.append(f"Calculation: {self._number(quantity)} g × {per_100g} kcal/100 g = {calories} kcal.")
            elif source == "manual":
                basis = self._clean(receipt.get("basis"), 180)
                if basis.startswith("unverified source label ignored"):
                    lines.append(f"Basis: {basis}. Send a correction with the food, serving, or calories if this is wrong.")
                else:
                    serving = self._serving(quantity, unit)
                    lines.append(f"Basis: user-provided {calories} kcal" + (f" for {serving}." if serving else "."))
            elif source == "ai_estimate" and trusted_ai_estimate:
                basis = self._clean(receipt.get("basis"), 180)
                detail = f" Basis: {basis}." if basis else ""
                lines.append(f"Estimate recorded; no verified source or URL is available.{detail}")
            else:
                lines.append(
                    "No verified source calculation is available."
                    + " Send a correction with the food, serving, or calories if this is wrong."
                )
            return lines

        candidate = self._candidate(evidence.selected_candidate, evidence.source_name)
        grams = self._number(evidence.quantity_grams)
        url = self._clean(evidence.source_url, 900) if evidence.source_url else None
        source_state = self._source_state(evidence.source_cache_hit, evidence.source_fetched_at)
        confidence = self._clean(evidence.confidence, 32)
        lines = [
            f"Logged: {description} — {evidence.total_calories} kcal",
            f"Food: {candidate}; {grams} g × {evidence.calories_per_100g} kcal/100 g = {evidence.total_calories} kcal.",
            f"Verified source: {self._clean(evidence.source_name, 120)} ({source_state}); confidence: {confidence}.",
        ]
        if url:
            lines.append(f"Source: {url}")
        return lines

    def _media_lines(self, context: AgentContext) -> list[str]:
        """Expose server output without relabeling it as a model observation."""
        text = str(context.media_text or "").strip()[:500]
        if context.media_kind == "voice" and text:
            lines = [f"I heard: {text}"]
            if context.media_caption:
                lines.append(f"Voice caption: {self._clean(context.media_caption, 180)}")
            return lines
        if context.media_kind == "voice_caption_only":
            return [f"Voice caption (no transcript): {self._clean(context.media_caption, 180)}"] if context.media_caption else ["Voice note had no usable transcript."]
        if context.media_kind == "photo" and text:
            return self._photo_lines(text)
        return []

    def _photo_lines(self, assessment: str) -> list[str]:
        sections: dict[str, str] = {}
        for line in assessment.splitlines():
            label, separator, value = line.partition(":")
            if separator and label.strip().lower() in {"interpretation", "estimate", "confidence", "question"}:
                sections[label.strip().lower()] = self._clean(value, 240)
        if not sections:
            return [f"Photo interpretation: {self._clean(assessment, 360)}"]
        lines = []
        if sections.get("interpretation"):
            lines.append(f"Photo: {sections['interpretation']}")
        details = "; ".join(
            f"{label}: {sections[label]}" for label in ("estimate", "confidence") if sections.get(label)
        )
        if details:
            lines.append(details.capitalize() + ".")
        question = sections.get("question")
        if question and question.lower() != "none":
            lines.append(f"Question: {question}")
        return lines

    @staticmethod
    def _candidate(raw: object, fallback: str) -> str:
        try:
            candidate = json.loads(str(raw))
            if isinstance(candidate, dict):
                name = candidate.get("name")
                brand = candidate.get("brand")
                return JournalAgent._clean(" ".join(str(v) for v in (name, brand) if v), 180) or fallback
        except (TypeError, ValueError):
            pass
        return JournalAgent._clean(raw, 180) or fallback

    @staticmethod
    def _source_state(cache_hit: bool, fetched_at: datetime | None) -> str:
        if not cache_hit:
            return "fetched from provider"
        if fetched_at is not None and fetched_at <= datetime.now(UTC) - timedelta(days=30):
            return "cached/stale; not a live lookup"
        return "cached; not a live lookup"

    @staticmethod
    def _clean(value: object, limit: int) -> str:
        return " ".join(str(value or "").split())[:limit]

    @staticmethod
    def _number(value: object) -> str:
        try:
            number = float(value)
            return str(int(number)) if number.is_integer() else f"{number:g}"
        except (TypeError, ValueError):
            return "?"

    def _serving(self, quantity: object, unit: str) -> str:
        if quantity is None or not unit or unit == "unspecified":
            return ""
        return f"{self._number(quantity)} {unit}"

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
