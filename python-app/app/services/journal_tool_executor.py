"""Deterministic tool executor — v2.0 thin dispatcher.

The handler logic lives in focused modules under app/tools/ (issue #105).
This class holds shared state (OFF client, SearxNG, Browserless, daily status
refresh, web search cache) and dispatches tool calls to the module handlers.

The _quote_item, _quote_summary, _item_summary, _cache_selected,
_record_packaged_evidence, _synchronize_items_after_edit, _restore_from,
_settings_for, _for_today, _search_entries_impl, and _owned_quote methods
remain here because they are shared state or helper logic used by multiple
modules. The SSRF guard (_is_safe_external_url, _resolve_safe_final_url) moved
to nutrition.py."""

import json
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_schemas import tool_definitions
from app.db.constraints import MAX_CALORIES, MAX_TOOL_ARGUMENT_CHARS, MIN_CALORIES
from app.db.models.entries import FoodEntry, FoodItem
from app.db.models.nutrition import (
    NutritionEvidence,
    NutritionSourceCache,
    PendingNutritionQuote,
)
from app.domain.agent_types import (
    AgentContext,
    AgentToolResult,
    ToolCall,
)
from app.domain.journal_intent import MealItem
from app.integrations.openfoodfacts_types import (
    NullOpenFoodFactsClient,
    OpenFoodFactsClient,
)
from app.repositories import (
    food_entry_repo,
    food_user_repo,
    nutrition_source_cache_repo,
    pending_nutrition_quote_repo,
)
from app.tools.journal_actions import _action_success as _action_success_impl
from app.tools.journal_actions import _create_action as _create_action_impl
from app.tools.nutrition import (
    _is_safe_external_url,
    _resolve_safe_final_url,
)
from app.tools.registry import HANDLERS
from app.tools.shared import (  # noqa: F401
    ValidationError,
    _derived_calories,
    _resolve_meal_instant,
    _search_date,
)

RefreshDailyStatus = Callable[[AsyncSession, Any, str], Awaitable[None]]
_TOOL_SCHEMAS = {definition["function"]["name"]: definition["function"]["parameters"] for definition in tool_definitions()}


def _unknown_argument_path(schema: dict[str, Any], value: object, path: str = "") -> str | None:
    if not isinstance(value, dict) or schema.get("type") != "object":
        if isinstance(value, list) and schema.get("type") == "array":
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    unknown = _unknown_argument_path(item_schema, item, f"{path}[{index}]")
                    if unknown:
                        return unknown
        return None

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None
    for key in value:
        if key not in properties:
            return f"{path}.{key}" if path else key
    for key, item in value.items():
        property_schema = properties.get(key)
        if isinstance(property_schema, dict):
            unknown = _unknown_argument_path(property_schema, item, f"{path}.{key}" if path else key)
            if unknown:
                return unknown
    return None


async def _noop_refresh(session: AsyncSession, user, chat_id: str) -> None:
    return None


# Purely conversational messages that must never trigger journal mutations.
# This is a deterministic safety guard — the prompt instructs the model, but
# the executor enforces it so a prompt-hallucinated mutation on "thanks"
# cannot persist food the user never asked to log.
_CONVERSATIONAL_RE = re.compile(
    r"^(?:mul\s*țumesc|mul\W*umesc|mersi|multumesc|thanks|thank you|thx|ok\b|ok\W*|"
    r"bine|great|super|perfect|de acord|agree|da\b|yes\b|yeah|yep|salut\b|hi\b|hello\b|"
    r"hey\b|servus\b|buna\b|bună\b|ceau\b|pa\b|la revedere|bye\b|gata|"
    r"no problem|np|cool|nice|foarte bine|foarte bun|excelent|"
    r"👍|👌|🙂|😄|😅|😊|💪|❤️|🔥)\W*$",
    re.IGNORECASE,
)


def _is_conversational_message(message: str) -> bool:
    """True when the user's message is a greeting, thanks, or bare acknowledgment
    with no food-logging intent. Emoji-only messages are conversational."""
    if not message:
        return True
    stripped = message.strip()
    if not stripped:
        return True
    return len(stripped) <= 30 and bool(_CONVERSATIONAL_RE.match(stripped))


class JournalToolExecutor:
    def __init__(
        self,
        off: OpenFoodFactsClient | None = None,
        searxng=None,
        browserless=None,
        refresh_daily_status: RefreshDailyStatus = _noop_refresh,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.off = off or NullOpenFoodFactsClient()
        self.searxng = searxng
        self.browserless = browserless
        self.refresh_daily_status = refresh_daily_status
        self._http = http
        self._web_search_cache: dict[str, tuple[datetime, list[dict[str, str]]]] = {}

    async def execute(self, session: AsyncSession, context: AgentContext, call: ToolCall, todos: list[str]) -> AgentToolResult:
        raw_arguments = call.arguments
        if raw_arguments is None or raw_arguments == "":
            raw_arguments = "{}"
        if not isinstance(raw_arguments, str) or len(raw_arguments) > MAX_TOOL_ARGUMENT_CHARS:
            return AgentToolResult.failure("VALIDATION_ERROR", "The supplied details are invalid.")
        try:
            args = json.loads(raw_arguments)
        except (TypeError, ValueError, RecursionError):
            return AgentToolResult.failure("VALIDATION_ERROR", "The supplied details are invalid.")
        if not isinstance(args, dict):
            return AgentToolResult.failure("VALIDATION_ERROR", "The supplied details are invalid.")

        if not isinstance(call.name, str):
            return AgentToolResult.failure("VALIDATION_ERROR", "That tool is not available.")
        # Deterministic guard: a purely conversational message (greeting, thanks,
        # bare acknowledgment) must never trigger a journal mutation, even if
        # the model hallucinates logging intent from conversation memory.
        if call.name == "apply_journal_actions" and _is_conversational_message(context.message):
            return AgentToolResult.failure(
                "NOT_A_LOGGING_REQUEST",
                "The current message is conversational and does not request food logging.",
            )
        handler = HANDLERS.get(call.name)
        if handler is None:
            return AgentToolResult.failure("VALIDATION_ERROR", "That tool is not available.")
        schema = _TOOL_SCHEMAS.get(call.name)
        if schema is not None:
            unknown = _unknown_argument_path(schema, args)
            if unknown:
                return AgentToolResult.failure("VALIDATION_ERROR", "The supplied details are invalid.")
        try:
            return await handler(self, session, context, args, todos)
        except ValidationError as failure:
            return AgentToolResult.failure("VALIDATION_ERROR", str(failure) or "The supplied details are invalid.")

    # --- SSRF guards (delegated to nutrition module) ---------------------

    _is_safe_external_url = staticmethod(_is_safe_external_url)
    _resolve_safe_final_url = staticmethod(_resolve_safe_final_url)

    # --- action helpers (delegated to journal_actions module) ------------

    _action_success = staticmethod(_action_success_impl)

    async def _create_action(self, session, context, args, change_set, now, timezone_name):
        return await _create_action_impl(self, session, context, args, change_set, now, timezone_name)

    # --- shared state helpers used by tool modules -----------------------

    async def _settings_for(self, session: AsyncSession, context: AgentContext):
        return await food_user_repo.get_settings(session, context.user.id)

    async def _for_today(self, session: AsyncSession, context: AgentContext) -> list[FoodEntry]:
        settings = await self._settings_for(session, context)
        from zoneinfo import ZoneInfo

        zone = ZoneInfo(settings.timezone)
        today = context.started_at.astimezone(zone).date()
        start, end = food_entry_repo.day_bounds(today, zone)
        return await food_entry_repo.find_between(session, context.user, start, end)

    async def _search_entries_impl(self, session, context, q, date_arg, from_arg, to_arg, zone, today) -> list[FoodEntry]:
        rows: list[FoodEntry]
        if date_arg:
            day = _search_date(context, date_arg, today)
            start, end = food_entry_repo.day_bounds(day, zone)
            rows = await food_entry_repo.find_between(session, context.user, start, end)
        elif from_arg or to_arg:
            start_date = _search_date(context, from_arg or to_arg, today)
            end_date = _search_date(context, to_arg or from_arg, today)
            if end_date < start_date:
                return []
            start, _ = food_entry_repo.day_bounds(start_date, zone)
            _, end = food_entry_repo.day_bounds(end_date, zone)
            rows = await food_entry_repo.find_between(session, context.user, start, end)
        else:
            rows = await self._for_today(session, context) if not q else await food_entry_repo.search_by_term(session, context.user, q)

        if q and (date_arg or from_arg or to_arg):
            needle = q.lower()
            rows = [r for r in rows if needle in r.original_message.lower()]
        return rows

    async def _owned_quote(self, session, context, quote_id, expected_type) -> PendingNutritionQuote | None:
        if quote_id is None:
            return None
        now = datetime.now(UTC)
        quote = await pending_nutrition_quote_repo.lock_owned_active(session, quote_id, context.user, now)
        if quote is None or quote.quote_type != expected_type:
            return None
        return quote

    def _quote_item(self, quote: PendingNutritionQuote) -> MealItem:
        total = _derived_calories(float(quote.grams), quote.calories_per_100g)
        return MealItem(
            name=quote.product_name,
            grams=float(quote.grams),
            total_calories=total,
            calories_per_100g=quote.calories_per_100g,
            barcode=quote.barcode,
        )

    def _quote_summary(self, quote: PendingNutritionQuote) -> dict[str, Any]:
        item = self._quote_item(quote)
        result = {
            "quoteId": str(quote.quote_id),
            "name": quote.product_name,
            "brand": quote.brand,
            "grams": float(quote.grams),
            "caloriesPer100g": quote.calories_per_100g,
            "totalCalories": item.total_calories,
            "type": quote.quote_type,
        }
        if quote.barcode:
            result["barcode"] = quote.barcode
        if quote.source_url:
            result["sourceUrl"] = quote.source_url
        if quote.quote_type == "PACKAGED_MATCH":
            result["evidenceClaim"] = "verified_source"
        return result

    def _item_summary(self, item: MealItem, source: str, confidence: str) -> dict[str, Any]:
        return {"name": item.name, "grams": item.grams, "caloriesPer100g": item.calories_per_100g, "totalCalories": item.total_calories, "source": source, "confidence": confidence}

    async def _cache_selected(self, session: AsyncSession, quote: PendingNutritionQuote) -> None:
        if not quote.barcode:
            return
        existing = await nutrition_source_cache_repo.find_by_barcode(session, quote.barcode)
        now = datetime.now(UTC)
        if existing is None:
            session.add(NutritionSourceCache(barcode=quote.barcode, product_name=quote.product_name, calories_per_100g=quote.calories_per_100g, source_url=quote.source_url or "", fetched_at=now))
        else:
            existing.product_name = quote.product_name
            existing.calories_per_100g = quote.calories_per_100g
            existing.source_url = quote.source_url or ""
            existing.fetched_at = now

    def _record_packaged_evidence(
        self, session: AsyncSession, entry: FoodEntry, item: FoodItem, quote: PendingNutritionQuote, captured_at: datetime
    ) -> NutritionEvidence:
        total = _derived_calories(float(quote.grams), quote.calories_per_100g)
        candidate = json.dumps(
            {"name": quote.product_name, "brand": quote.brand, "barcode": quote.barcode},
            separators=(",", ":"),
            sort_keys=True,
        )
        grams = Decimal(str(quote.grams))
        derivation = f"round({grams} g × {quote.calories_per_100g} kcal / 100 g) = {total} kcal"
        evidence = NutritionEvidence(
            evidence_id=uuid.uuid4(), food_entry_id=entry.id, food_item_id=item.id,
            selected_quote_id=quote.quote_id, provider="open_food_facts", source_name="Open Food Facts",
            source_url=quote.source_url, source_query=quote.source_query, selected_candidate=candidate,
            quantity_grams=grams, calories_per_100g=quote.calories_per_100g, total_calories=total,
            derivation=derivation, confidence="high", source_fetched_at=quote.source_fetched_at,
            source_cache_hit=quote.source_cache_hit, captured_at=captured_at,
        )
        session.add(evidence)
        return evidence

    def _record_ai_estimate_evidence(
        self, session: AsyncSession, entry: FoodEntry, item: FoodItem, quote: PendingNutritionQuote, captured_at: datetime
    ) -> NutritionEvidence:
        total = _derived_calories(float(quote.grams), quote.calories_per_100g)
        candidate = json.dumps(
            {"name": quote.product_name, "basis": quote.estimate_basis or "AI estimate"},
            separators=(",", ":"),
            sort_keys=True,
        )
        grams = Decimal(str(quote.grams))
        derivation = f"{grams} g × {quote.calories_per_100g} kcal/100 g = {total} kcal"
        evidence = NutritionEvidence(
            evidence_id=uuid.uuid4(), food_entry_id=entry.id, food_item_id=item.id,
            selected_quote_id=quote.quote_id, provider="ai_estimate", source_name="AI estimate",
            source_url=None, source_query=None, selected_candidate=candidate,
            quantity_grams=grams, calories_per_100g=quote.calories_per_100g, total_calories=total,
            derivation=derivation, confidence="estimate", source_fetched_at=None,
            source_cache_hit=False, captured_at=captured_at,
        )
        session.add(evidence)
        return evidence

    def _synchronize_items_after_edit(self, current: list[FoodItem], description: str, total_calories: int) -> None:
        if not current:
            return
        if len(current) == 1:
            current[0].revise(description, total_calories)
            return
        old_total = sum(i.calories or 0 for i in current)
        assigned = 0
        for index, item in enumerate(current):
            if index == len(current) - 1:
                revised = total_calories - assigned
            elif old_total <= 0:
                revised = 0
            else:
                revised = int((total_calories * max(0, item.calories or 0)) / old_total)
            revised = max(MIN_CALORIES, min(MAX_CALORIES, revised))
            assigned += revised
            item.revise_calories(revised)

    @staticmethod
    def _restore_from(entry: FoodEntry, before: dict[str, Any]) -> None:
        entry.original_message = before["originalMessage"]
        entry.eaten_at = datetime.fromisoformat(before["eatenAt"])
        entry.calories = before["calories"]
        entry.nutrition_source = before["nutritionSource"]
        entry.confidence = before["confidence"]
        entry.deleted_at = datetime.fromisoformat(before["deletedAt"]) if before.get("deletedAt") else None
