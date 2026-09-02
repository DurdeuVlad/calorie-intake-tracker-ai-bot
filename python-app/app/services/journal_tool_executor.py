"""Deterministic tool business logic, ported from JournalToolExecutor.java.

The `create_food_entry` tool (a legacy multi-item creation path) is
intentionally NOT ported: it was never exposed in toolDefinitions(), so the
model could never call it in production -- it was unreachable dead code from
the agent's perspective, in the same family as the non-agent fallback path
this rewrite already dropped by explicit decision.
"""

import json
import re
import socket
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, time, timedelta
from datetime import date as date_type
from decimal import Decimal
from typing import Any, ClassVar

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entries import FoodEntry, FoodItem
from app.db.models.journal_changes import JournalChangeSet
from app.db.models.nutrition import (
    NutritionEvidence,
    NutritionSourceCache,
    PendingNutritionQuote,
    PrivateFood,
)
from app.domain import journal_entry_snapshot as snapshot
from app.domain.agent_types import (
    AgentContext,
    AgentToolFailure,
    AgentToolResult,
    ToolCall,
)
from app.domain.journal_intent import MealItem
from app.domain.quantity_unit import QuantityUnit
from app.integrations.openfoodfacts_types import (
    NullOpenFoodFactsClient,
    OpenFoodFactsClient,
)
from app.repositories import (
    feedback_repo,
    food_entry_repo,
    food_item_repo,
    food_user_repo,
    journal_change_set_repo,
    nutrition_source_cache_repo,
    pending_nutrition_quote_repo,
    private_food_repo,
)
from app.services import nutrition_resolver, openfoodfacts_cache

MAX_ACTIONS_PER_BATCH = 20
MAX_REDIRECTS = 5
WEB_SEARCH_CACHE_TTL = timedelta(days=1)
MAX_WEB_SEARCH_CACHE_ENTRIES = 256
MAX_WEB_SEARCH_QUERY_CHARS = 256
MAX_WEB_SEARCH_TITLE_CHARS = 256
MAX_WEB_SEARCH_URL_CHARS = 1024
MAX_WEB_SEARCH_SNIPPET_CHARS = 1024
_DATE_WORDS_TODAY = {"today", "azi", "astăzi", "astazi"}
_DATE_WORDS_YESTERDAY = {"yesterday", "yersterday", "ieri"}
_VALID_SOURCES = {"manual", "private", "open_food_facts", "open_food_facts_estimate", "ai_estimate", "mixed"}
_VALID_CONFIDENCE = {"high", "estimate", "unknown"}
_LOCAL_TIME_RE = re.compile(
    r"^(?P<hour>\d{1,2})(?::(?P<minute>\d{1,2})(?::(?P<second>\d{1,2}))?)?$"
)

RefreshDailyStatus = Callable[[AsyncSession, Any, str], Awaitable[None]]


async def _noop_refresh(session: AsyncSession, user, chat_id: str) -> None:
    return None


class ValidationError(ValueError):
    pass


def _str(args: dict, key: str) -> str | None:
    value = args.get(key)
    return None if value is None else str(value)


def _bounded_text(value: object, limit: int) -> str:
    return str(value)[:limit]


def _int_required(args: dict, key: str) -> int:
    value = args.get(key)
    if value is None:
        raise ValidationError(f"{key} is required")
    return int(value)


def _decimal_number(args: dict, key: str) -> float | None:
    value = args.get(key)
    return None if value is None else float(value)


def _quote_id(args: dict) -> uuid.UUID | None:
    raw = _str(args, "quoteId")
    if raw is None:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def _meal_item(args: dict) -> MealItem:
    return MealItem(
        name=_str(args, "name"),
        grams=_decimal_number(args, "grams"),
        total_calories=int(args["totalCalories"]) if args.get("totalCalories") is not None else None,
        calories_per_100g=int(args["caloriesPer100g"]) if args.get("caloriesPer100g") is not None else None,
        barcode=_str(args, "barcode"),
    )


def _valid_item(item: MealItem | None) -> bool:
    return item is not None and bool(item.name) and item.grams is not None and item.grams > 0


def _valid_calories_per_100g(value: int | None) -> bool:
    return value is not None and 0 < value <= 10000


def _quantity_unit(raw: str | None, quantity: float | None) -> str:
    if not raw:
        return QuantityUnit.UNSPECIFIED.value if quantity is None else QuantityUnit.PORTION.value
    return QuantityUnit.from_database_value(raw).value


def _normalize(raw: str | None, fallback: str, allowed: set[str]) -> str:
    value = (raw or fallback).lower()
    return value if value in allowed else fallback


def _unverified_source_claim(raw: str | None) -> bool:
    """Only server-issued quotes may establish a non-manual nutrition source."""
    return raw is not None and raw.strip().lower() != "manual"


def _summary(entry: FoodEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "calories": entry.calories,
        "eatenAt": entry.eaten_at.isoformat() if entry.eaten_at else None,
        "description": entry.original_message,
    }


def _search_date(context: AgentContext, requested: str | None, today: date_type) -> date_type:
    value = (requested or "today").strip().lower()
    if value in _DATE_WORDS_TODAY:
        return today
    if value in _DATE_WORDS_YESTERDAY:
        return today - timedelta(days=1)
    try:
        return date_type.fromisoformat(value)
    except ValueError:
        raise ValidationError("Use today, yesterday, or an ISO date.")


def _parse_local_time(value: str) -> time:
    """Parse compact local-time forms extracted from natural-language input.

    Hour-only input is intentional: Romanian phrases such as "pe ora 9" are
    unambiguous and commonly arrive from the model as ``"9"``. Keep the
    accepted surface narrow so arbitrary natural-language text is still
    rejected at this deterministic boundary.
    """
    match = _LOCAL_TIME_RE.fullmatch(value.strip())
    if match is None:
        raise ValidationError("Use a valid local time such as 18:30.")
    try:
        return time(
            hour=int(match.group("hour")),
            minute=int(match.group("minute") or 0),
            second=int(match.group("second") or 0),
        )
    except ValueError as failure:
        raise ValidationError("Use a valid local time such as 18:30.") from failure


def _resolve_meal_instant(
    context: AgentContext, timezone_name: str, requested_date: str | None, requested_time: str | None, existing: datetime | None = None
) -> datetime:
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(timezone_name)
    base = context.started_at
    today = base.astimezone(zone).date()

    value = (requested_date or "today").strip().lower()
    if value in _DATE_WORDS_TODAY:
        target_date = today
    elif value in _DATE_WORDS_YESTERDAY:
        target_date = today - timedelta(days=1)
    else:
        try:
            target_date = date_type.fromisoformat(value)
        except ValueError:
            raise ValidationError("Use today, yesterday, or an ISO date.")
    if target_date > today:
        raise ValidationError("Future meal dates are not allowed.")

    if requested_time:
        target_time = _parse_local_time(requested_time)
    elif existing is not None:
        target_time = existing.astimezone(zone).time()
    else:
        target_time = base.astimezone(zone).time()

    local_naive = datetime.combine(target_date, target_time)
    aware = local_naive.replace(tzinfo=zone, fold=0)
    # Detect a DST "spring forward" gap: a nonexistent local time round-trips to a
    # different wall clock once normalized through UTC.
    roundtrip = aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    if roundtrip != local_naive:
        raise ValidationError("That local time does not exist because of daylight-saving time. Use another time.")

    result = aware.astimezone(UTC)
    if result > base:
        raise ValidationError("Future meal times are not allowed.")
    return result


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
        try:
            args: dict[str, Any] = json.loads(call.arguments or "{}")
        except json.JSONDecodeError:
            return AgentToolResult.failure("VALIDATION_ERROR", "The supplied details are invalid.")

        try:
            handler = self._HANDLERS.get(call.name)
            if handler is None:
                return AgentToolResult.failure("VALIDATION_ERROR", "That tool is not available.")
            return await handler(self, session, context, args, todos)
        except ValidationError:
            return AgentToolResult.failure("VALIDATION_ERROR", "The supplied details are invalid.")

    # --- simple read tools -------------------------------------------------

    async def _settings_for(self, session: AsyncSession, context: AgentContext):
        return await food_user_repo.get_settings(session, context.user.id)

    async def _for_today(self, session: AsyncSession, context: AgentContext) -> list[FoodEntry]:
        settings = await self._settings_for(session, context)
        from zoneinfo import ZoneInfo

        zone = ZoneInfo(settings.timezone)
        today = food_entry_repo.local_tracking_date(datetime.now(zone), zone, settings.day_boundary_hour)
        start, end = food_entry_repo.day_bounds(today, zone, settings.day_boundary_hour)
        return await food_entry_repo.find_between(session, context.user, start, end)

    async def _today(self, session, context, args, todos) -> AgentToolResult:
        rows = await self._for_today(session, context)
        total = sum(r.calories or 0 for r in rows)
        settings = await self._settings_for(session, context)
        target = settings.calorie_target
        return AgentToolResult.success({"calories": total, "entries": len(rows), "target": "unset" if target is None else target})

    async def _search(self, session, context, args, todos) -> AgentToolResult:
        settings = await self._settings_for(session, context)
        q = _str(args, "query")
        date_arg = _str(args, "date")
        from_arg = _str(args, "fromDate")
        to_arg = _str(args, "toDate")
        from zoneinfo import ZoneInfo

        zone = ZoneInfo(settings.timezone)
        today = food_entry_repo.local_tracking_date(context.started_at, zone, settings.day_boundary_hour)

        rows: list[FoodEntry]
        if date_arg:
            day = _search_date(context, date_arg, today)
            start, end = food_entry_repo.day_bounds(day, zone, settings.day_boundary_hour)
            rows = await food_entry_repo.find_between(session, context.user, start, end)
        elif from_arg or to_arg:
            start_date = _search_date(context, from_arg or to_arg, today)
            end_date = _search_date(context, to_arg or from_arg, today)
            if end_date < start_date:
                return AgentToolResult.failure("VALIDATION_ERROR", "The end date cannot be before the start date.")
            start, _ = food_entry_repo.day_bounds(start_date, zone, settings.day_boundary_hour)
            _, end = food_entry_repo.day_bounds(end_date, zone, settings.day_boundary_hour)
            rows = await food_entry_repo.find_between(session, context.user, start, end)
        else:
            rows = await self._for_today(session, context) if not q else await food_entry_repo.search_by_term(session, context.user, q)

        if q and (date_arg or from_arg or to_arg):
            needle = q.lower()
            rows = [r for r in rows if needle in r.original_message.lower()]

        return AgentToolResult.success({"entries": [_summary(r) for r in rows[:10]]})

    async def _entry(self, session, context, args, todos) -> AgentToolResult:
        entry = await food_entry_repo.find_by_id_and_user(session, _int_required(args, "entryId"), context.user)
        if entry is None:
            return AgentToolResult.failure("NOT_FOUND", "No matching journal entry exists.")
        return AgentToolResult.success({"entry": _summary(entry)})

    async def _settings_tool(self, session, context, args, todos) -> AgentToolResult:
        s = await self._settings_for(session, context)
        return AgentToolResult.success(
            {
                "timezone": s.timezone,
                "calorieTarget": "unset" if s.calorie_target is None else s.calorie_target,
                "reportsEnabled": s.reports_enabled,
                "dayBoundaryHour": s.day_boundary_hour,
                "dayBoundaryReminderEnabled": s.day_boundary_reminder_enabled,
            }
        )

    # --- nutrition -----------------------------------------------------

    async def _resolve(self, session, context, args, todos) -> AgentToolResult:
        requested = _meal_item(args)
        resolved = await nutrition_resolver.resolve(session, context.user, requested, self.off)
        item = resolved.item
        if item is None or item.total_calories is None:
            return AgentToolResult.failure("NOT_FOUND", "Nutrition could not be resolved; search packaged food or estimate it.")
        return AgentToolResult.success(
            {
                "name": item.name,
                "grams": item.grams,
                "totalCalories": item.total_calories,
                "caloriesPer100g": item.calories_per_100g if item.calories_per_100g is not None else "unknown",
                "source": resolved.source,
            }
        )

    async def _private_food(self, session, context, args, todos) -> AgentToolResult:
        name = _str(args, "name")
        food = await private_food_repo.find_by_user_and_name_ignore_case(session, context.user, name) if name else None
        if food is None:
            return AgentToolResult.failure("NOT_FOUND", "No household food matches that name.")
        return AgentToolResult.success({"name": food.name, "caloriesPer100g": food.calories_per_100g})

    def _quote_item(self, quote: PendingNutritionQuote) -> MealItem:
        total = round(float(quote.grams) * quote.calories_per_100g / 100.0)
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
        # This is provenance returned by a server-side Open Food Facts client;
        # callers cannot supply or replace it in an action.
        if quote.quote_type == "PACKAGED_MATCH":
            result["evidenceClaim"] = "verified_source"
        return result

    def _item_summary(self, item: MealItem, source: str, confidence: str) -> dict[str, Any]:
        return {"name": item.name, "grams": item.grams, "caloriesPer100g": item.calories_per_100g, "totalCalories": item.total_calories, "source": source, "confidence": confidence}

    async def _packaged_food(self, session, context, args, todos) -> AgentToolResult:
        if isinstance(self.off, NullOpenFoodFactsClient):
            return AgentToolResult.failure("TEMPORARY_FAILURE", "Packaged-food search is unavailable.")
        name = _str(args, "name")
        grams = _decimal_number(args, "grams")
        if not name or grams is None or grams <= 0:
            return AgentToolResult.failure("VALIDATION_ERROR", "A food name and positive grams are required.")
        batch_id = uuid.uuid4()
        products = []
        now = datetime.now(UTC)
        lookup = await openfoodfacts_cache.packaged_name(session, self.off, name, _str(args, "brand"), now)
        if lookup.status in {"RATE_LIMITED", "TEMPORARY_FAILURE"}:
            return AgentToolResult.failure("TEMPORARY_FAILURE", "Packaged-food lookup is temporarily unavailable; please retry later.")
        for result in lookup.value or []:
            quote = PendingNutritionQuote(
                quote_id=uuid.uuid4(), batch_id=batch_id, user_id=context.user.id, quote_type="PACKAGED_MATCH",
                product_name=result.product_name, brand=result.brand, grams=Decimal(str(grams)),
                calories_per_100g=result.calories_per_100g, barcode=result.barcode, source_url=result.source_url,
                source_query=" ".join(part for part in (name.strip(), (_str(args, "brand") or "").strip()) if part),
                source_fetched_at=lookup.source_fetched_at, source_cache_hit=lookup.cache_hit,
                created_at=now, expires_at=now + timedelta(minutes=30),
            )
            session.add(quote)
            await session.flush()
            products.append(self._quote_summary(quote))
        if not products:
            return AgentToolResult.failure("NOT_FOUND", "No usable packaged-food result was found.")
        return AgentToolResult.success({"products": products})

    async def _pending_quotes(self, session, context, args, todos) -> AgentToolResult:
        now = datetime.now(UTC)
        first = await pending_nutrition_quote_repo.find_first_by_type(session, context.user, "PACKAGED_MATCH", now)
        if first is None:
            return AgentToolResult.failure("NOT_FOUND", "There are no pending nutrition choices.")
        batch = await pending_nutrition_quote_repo.find_by_batch(session, context.user, first.batch_id, now)
        rows = [self._quote_summary(q) for q in batch]
        if not rows:
            return AgentToolResult.failure("NOT_FOUND", "There are no pending nutrition choices.")
        return AgentToolResult.success({"quotes": rows})

    async def _owned_quote(self, session, context, quote_id: uuid.UUID | None, expected_type: str) -> PendingNutritionQuote | None:
        if quote_id is None:
            return None
        now = datetime.now(UTC)
        quote = await pending_nutrition_quote_repo.lock_owned_active(session, quote_id, context.user, now)
        if quote is None or quote.quote_type != expected_type:
            return None
        return quote

    async def _select_packaged(self, session, context, args, todos) -> AgentToolResult:
        quote = await self._owned_quote(session, context, _quote_id(args), "PACKAGED_MATCH")
        if quote is None:
            return AgentToolResult.failure("NOT_FOUND", "That packaged-food choice is unavailable or expired.")
        return AgentToolResult.success({"quoteId": str(quote.quote_id), "item": self._item_summary(self._quote_item(quote), "open_food_facts", "high"), "source": "Open Food Facts", "evidenceClaim": "verified_source"})

    async def _estimate_food(self, session, context, args, todos) -> AgentToolResult:
        item = _meal_item(args)
        if not _valid_item(item) or not _valid_calories_per_100g(item.calories_per_100g):
            return AgentToolResult.failure("VALIDATION_ERROR", "An estimate needs a food name, positive grams, and calories per 100 g between 1 and 10000.")
        basis = _str(args, "basis") or "AI estimate"
        now = datetime.now(UTC)
        quote = PendingNutritionQuote(
            quote_id=uuid.uuid4(), batch_id=uuid.uuid4(), user_id=context.user.id, quote_type="AI_ESTIMATE",
            product_name=item.name, grams=Decimal(str(item.grams)), calories_per_100g=item.calories_per_100g,
            estimate_basis=basis, created_at=now, expires_at=now + timedelta(minutes=30),
        )
        session.add(quote)
        await session.flush()
        return AgentToolResult.success({"quoteId": str(quote.quote_id), "item": self._item_summary(self._quote_item(quote), "ai_estimate", "estimate"), "basis": basis})

    # --- web tools (Phase 6 wires real clients; graceful degradation until then) ---

    async def _search_web(self, session, context, args, todos) -> AgentToolResult:
        if self.searxng is None:
            return AgentToolResult.failure("TEMPORARY_FAILURE", "Web search is unavailable.")
        raw_query = _str(args, "query")
        if not raw_query:
            return AgentToolResult.failure("VALIDATION_ERROR", "A search query is required.")
        query = " ".join(raw_query.split())
        if not query:
            return AgentToolResult.failure("VALIDATION_ERROR", "A search query is required.")
        cache_key = query.lower()
        if len(cache_key) > MAX_WEB_SEARCH_QUERY_CHARS:
            return AgentToolResult.failure("VALIDATION_ERROR", "The search query is too long.")
        now = datetime.now(UTC)
        cached = self._web_search_cache.get(cache_key)
        if cached is not None and cached[0] > now - WEB_SEARCH_CACHE_TTL:
            return AgentToolResult.success({"results": cached[1], "cached": True})

        results = await self.searxng.search(query)
        if not results:
            return AgentToolResult.failure("NOT_FOUND", "No web results were found.")
        grounded = [
            {
                "title": _bounded_text(r.title, MAX_WEB_SEARCH_TITLE_CHARS),
                "url": _bounded_text(r.url, MAX_WEB_SEARCH_URL_CHARS),
                "snippet": _bounded_text(r.snippet, MAX_WEB_SEARCH_SNIPPET_CHARS),
            }
            for r in results[:5]
        ]
        if len(self._web_search_cache) >= MAX_WEB_SEARCH_CACHE_ENTRIES:
            expired = [key for key, (cached_at, _) in self._web_search_cache.items() if cached_at <= now - WEB_SEARCH_CACHE_TTL]
            for key in expired:
                self._web_search_cache.pop(key, None)
            if len(self._web_search_cache) >= MAX_WEB_SEARCH_CACHE_ENTRIES:
                oldest_key = min(self._web_search_cache, key=lambda key: self._web_search_cache[key][0])
                self._web_search_cache.pop(oldest_key, None)
        self._web_search_cache[cache_key] = (now, grounded)
        return AgentToolResult.success({"results": grounded, "cached": False})

    def _is_safe_external_url(self, url: str) -> bool:
        try:
            parsed = httpx.URL(url)
            if parsed.scheme.lower() not in ("http", "https"):
                return False
            host = parsed.host
            if not host:
                return False
            infos = socket.getaddrinfo(host, None)
            import ipaddress

            for info in infos:
                addr = ipaddress.ip_address(info[4][0])
                if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_unspecified:
                    return False
            return True
        except Exception:  # noqa: BLE001
            return False

    async def _resolve_safe_final_url(self, url: str) -> str | None:
        """Walks up to MAX_REDIRECTS hops WITHOUT following them automatically,
        re-validating _is_safe_external_url at every hop -- see the module
        docstring's SSRF note. This is security-critical: do not replace with a
        client that auto-follows redirects."""
        current = url
        async with httpx.AsyncClient(follow_redirects=False, timeout=5.0) as client:
            for _hop in range(MAX_REDIRECTS + 1):
                if not self._is_safe_external_url(current):
                    return None
                try:
                    response = await client.get(current)
                except Exception:  # noqa: BLE001
                    return None
                if not (300 <= response.status_code < 400):
                    return current
                location = response.headers.get("location")
                if not location:
                    return None
                current = str(httpx.URL(current).join(location))
        return None

    async def _fetch_web_page(self, session, context, args, todos) -> AgentToolResult:
        if self.browserless is None:
            return AgentToolResult.failure("TEMPORARY_FAILURE", "Web page fetch is unavailable.")
        url = _str(args, "url")
        if not url:
            return AgentToolResult.failure("VALIDATION_ERROR", "A url is required.")
        if not self._is_safe_external_url(url):
            return AgentToolResult.failure("VALIDATION_ERROR", "That url cannot be fetched.")
        resolved = await self._resolve_safe_final_url(url)
        if resolved is None:
            return AgentToolResult.failure("VALIDATION_ERROR", "That url cannot be fetched.")
        text = await self.browserless.fetch_text(resolved)
        if text is None:
            return AgentToolResult.failure("NOT_FOUND", "That page could not be fetched.")
        return AgentToolResult.success({"url": resolved, "text": text})

    # --- todos ---------------------------------------------------------

    async def _plan_todos(self, session, context, args, todos: list[str]) -> AgentToolResult:
        raw = args.get("todos")
        if not isinstance(raw, list):
            return AgentToolResult.failure("VALIDATION_ERROR", "Provide a short todo list.")
        todos.clear()
        for value in raw:
            if value is not None and str(value).strip() and len(todos) < 6:
                todos.append(str(value))
        return AgentToolResult.success({"todos": list(todos)})

    async def _complete_todo(self, session, context, args, todos: list[str]) -> AgentToolResult:
        todo = _str(args, "todo")
        if todo is None or todo not in todos:
            return AgentToolResult.failure("NOT_FOUND", "That todo is not in the current run.")
        todos.remove(todo)
        return AgentToolResult.success({"todos": list(todos)})

    # --- journal mutation (apply_journal_actions) -----------------------

    async def _owned_entry(self, session, context, args) -> FoodEntry:
        if "entryId" not in args:
            raise ValidationError("An entry ID is required.")
        entry = await food_entry_repo.find_by_id_and_user(session, int(args["entryId"]), context.user)
        if entry is None:
            raise AgentToolFailure(AgentToolResult.failure("NOT_FOUND", "No matching journal entry exists."))
        return entry

    def _action_success(
        self, action_type: str, entry: FoodEntry, timezone_name: str, receipt: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        from zoneinfo import ZoneInfo

        local_date = entry.eaten_at.astimezone(ZoneInfo(timezone_name)).date()
        result = {
            "ok": True,
            "type": action_type,
            "entry": _summary(entry),
            "date": local_date.isoformat(),
            "nutritionSource": entry.nutrition_source,
            "nutritionConfidence": entry.confidence,
        }
        if receipt:
            result["receipt"] = receipt
        return result

    def _action_failure(self, action_type: str, message: str) -> dict[str, Any]:
        return {"ok": False, "type": action_type, "message": message}

    async def _create_action(self, session, context, args, change_set: JournalChangeSet | None, now: datetime, timezone_name: str) -> dict[str, Any]:
        description = _str(args, "description") or _str(args, "name")
        if not description:
            raise ValidationError("A description is required.")
        calories: int | None = int(args["calories"]) if "calories" in args and args["calories"] is not None else None
        requested_source = _str(args, "nutritionSource")
        source = _normalize(requested_source, "manual", _VALID_SOURCES)
        confidence = _normalize(_str(args, "nutritionConfidence"), "high" if source == "manual" else "estimate", _VALID_CONFIDENCE)
        quantity = _decimal_number(args, "quantity")
        unit = _quantity_unit(_str(args, "unit"), quantity)
        consumed: list[PendingNutritionQuote] = []
        receipt: dict[str, Any] = {"quantity": quantity, "unit": unit}
        unverified_source = args.get("quoteId") is None and _unverified_source_claim(requested_source)

        # A model can label an explicit number however it likes; it must not be
        # able to turn that into a verified external-source claim. Only an
        # owned, active quote can establish Open Food Facts provenance.
        if args.get("quoteId") is None and source in {"open_food_facts", "open_food_facts_estimate"}:
            raise ValidationError("Open Food Facts provenance requires a server-issued quoteId.")

        # Private foods and AI estimates do not have a caller-selectable
        # provenance token. Until they do, a model's label is just text: retain
        # the explicit calorie value as manual/unverified rather than storing a
        # claim the server cannot prove.
        if unverified_source:
            source = "manual"
            confidence = "unknown"

        if args.get("quoteId") is not None:
            quote_id = _quote_id(args)
            quote = await pending_nutrition_quote_repo.lock_owned_active(session, quote_id, context.user, datetime.now(UTC)) if quote_id else None
            if quote is None:
                raise AgentToolFailure(AgentToolResult.failure("NOT_FOUND", "The selected nutrition result is unavailable or expired."))
            quoted = self._quote_item(quote)
            calories = quoted.total_calories
            quantity = quoted.grams
            unit = QuantityUnit.G.value
            receipt.update({"quantity": quantity, "unit": unit})
            description = description or quoted.name
            source = "open_food_facts" if quote.quote_type == "PACKAGED_MATCH" else "ai_estimate"
            confidence = "high" if quote.quote_type == "PACKAGED_MATCH" else "estimate"
            if quote.quote_type == "AI_ESTIMATE":
                receipt.update({"caloriesPer100g": quote.calories_per_100g, "basis": quote.estimate_basis or "AI estimate"})
            consumed.append(quote)

        if calories is None or calories <= 0 or calories > 10000:
            raise ValidationError("Calories must be between 1 and 10000.")
        if quantity is not None and (quantity <= 0 or quantity > 100000):
            raise ValidationError("Quantity must be positive.")

        eaten_at = _resolve_meal_instant(context, timezone_name, _str(args, "date"), _str(args, "localTime"))
        entry = FoodEntry(user_id=context.user.id, original_message=description, eaten_at=eaten_at, calories=calories, nutrition_source=source, confidence=confidence, created_at=now)
        session.add(entry)
        await session.flush()
        item = FoodItem(
            entry_id=entry.id, name=description, quantity=Decimal(str(quantity)) if quantity is not None else None,
            quantity_unit=unit, calories=calories, nutrition_source=source, nutrition_confidence=confidence,
        )
        session.add(item)
        await session.flush()

        for quote in consumed:
            if quote.quote_type == "PACKAGED_MATCH":
                await self._cache_selected(session, quote)
                self._record_packaged_evidence(session, entry, item, quote, now)
            await session.delete(quote)

        after = snapshot.capture(entry, [item])
        if change_set is not None:
            change_set.add_mutation("CREATE", None, after)
        if unverified_source:
            receipt["basis"] = "unverified source label ignored; no confirmed source for this calorie value"
        elif source == "manual":
            receipt["basis"] = "user-provided calories"
        return self._action_success("CREATE", entry, timezone_name, receipt)

    def _record_packaged_evidence(
        self, session: AsyncSession, entry: FoodEntry, item: FoodItem, quote: PendingNutritionQuote, captured_at: datetime
    ) -> None:
        """Copy an ephemeral, server-selected quote into durable audit evidence.

        No action argument can influence provider, URL, candidate, basis, or
        derivation: those values originate with the stored quote/Open Food Facts
        response and the deterministic calorie calculation.
        """
        total = round(float(quote.grams) * quote.calories_per_100g / 100.0)
        candidate = json.dumps(
            {"name": quote.product_name, "brand": quote.brand, "barcode": quote.barcode},
            separators=(",", ":"),
            sort_keys=True,
        )
        grams = Decimal(str(quote.grams))
        derivation = f"round({grams} g × {quote.calories_per_100g} kcal / 100 g) = {total} kcal"
        session.add(
            NutritionEvidence(
                evidence_id=uuid.uuid4(), food_entry_id=entry.id, food_item_id=item.id,
                selected_quote_id=quote.quote_id, provider="open_food_facts", source_name="Open Food Facts",
                source_url=quote.source_url, source_query=quote.source_query, selected_candidate=candidate,
                quantity_grams=grams, calories_per_100g=quote.calories_per_100g, total_calories=total,
                derivation=derivation, confidence="high", source_fetched_at=quote.source_fetched_at,
                source_cache_hit=quote.source_cache_hit, captured_at=captured_at,
            )
        )

    async def _edit_action(self, session, context, args, change_set: JournalChangeSet | None, timezone_name: str) -> dict[str, Any]:
        entry = await self._owned_entry(session, context, args)
        current = await food_item_repo.find_by_entry(session, entry)
        before = snapshot.capture(entry, current)
        description = _str(args, "description") or entry.original_message
        calories = int(args["calories"]) if "calories" in args and args["calories"] is not None else entry.calories
        if calories is None or calories < 0 or calories > 10000:
            raise ValidationError("Calories must be between 0 and 10000.")
        entry.revise(description, calories)
        self._synchronize_items_after_edit(current, description, calories)
        after = snapshot.capture(entry, current)
        if change_set is not None:
            change_set.add_mutation("EDIT", before, after)
        return self._action_success("EDIT", entry, timezone_name)

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
            revised = max(0, min(10000, revised))
            assigned += revised
            item.revise_calories(revised)

    async def _move_action(self, session, context, args, change_set: JournalChangeSet | None, timezone_name: str) -> dict[str, Any]:
        entry = await self._owned_entry(session, context, args)
        current = await food_item_repo.find_by_entry(session, entry)
        before = snapshot.capture(entry, current)
        new_when = _resolve_meal_instant(context, timezone_name, _str(args, "date"), _str(args, "localTime"), entry.eaten_at)
        entry.move_to(new_when, context.started_at)
        after = snapshot.capture(entry, current)
        if change_set is not None:
            change_set.add_mutation("MOVE", before, after)
        return self._action_success("MOVE", entry, timezone_name)

    async def _delete_action(self, session, context, args, change_set: JournalChangeSet | None, now: datetime, timezone_name: str) -> dict[str, Any]:
        entry = await self._owned_entry(session, context, args)
        current = await food_item_repo.find_by_entry(session, entry)
        before = snapshot.capture(entry, current)
        entry.mark_deleted(now)
        after = snapshot.capture(entry, current)
        if change_set is not None:
            change_set.add_mutation("DELETE", before, after)
        return self._action_success("DELETE", entry, timezone_name)

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

    async def _apply_actions(self, session, context, args, todos) -> AgentToolResult:
        requested = args.get("actions")
        if not isinstance(requested, list) or not requested:
            return AgentToolResult.failure("VALIDATION_ERROR", "At least one journal action is required.")
        if len(requested) > MAX_ACTIONS_PER_BATCH:
            return AgentToolResult.failure("VALIDATION_ERROR", "A message may contain at most 20 journal actions.")

        settings = await self._settings_for(session, context)
        now = context.started_at
        await journal_change_set_repo.delete_expired(session, now)
        # Built in memory only -- NOT session.add()ed yet. A change set that ends
        # up with zero successful mutations must never touch the DB at all
        # (matches JournalChangeSet.start(...) in the Java predecessor, which is
        # only ever passed to changeSets.save(...) when changed > 0).
        change_set = JournalChangeSet(user_id=context.user.id, created_at=now, expires_at=now + timedelta(minutes=10))

        results: list[dict[str, Any]] = []
        changed = 0
        for raw in requested:
            if not isinstance(raw, dict):
                results.append(self._action_failure("ACTION", "Invalid journal action."))
                continue
            action_type = (raw.get("type") or "ACTION").upper()
            try:
                if action_type == "CREATE":
                    result = await self._create_action(session, context, raw, change_set, now, settings.timezone)
                elif action_type == "EDIT":
                    result = await self._edit_action(session, context, raw, change_set, settings.timezone)
                elif action_type == "MOVE":
                    result = await self._move_action(session, context, raw, change_set, settings.timezone)
                elif action_type == "DELETE":
                    result = await self._delete_action(session, context, raw, change_set, now, settings.timezone)
                else:
                    result = self._action_failure(action_type, "Unsupported journal action.")
                if result.get("ok"):
                    await session.flush()
                    changed += 1
                results.append(result)
            except AgentToolFailure as failure:
                results.append(self._action_failure(action_type, failure.result.user_hint or "The action was rejected."))
            except ValidationError as failure:
                results.append(self._action_failure(action_type, str(failure) or "The action details are invalid."))

        if changed > 0:
            session.add(change_set)
            await session.flush()
            await self.refresh_daily_status(session, context.user, context.chat_id)

        return AgentToolResult.success(
            {"results": results, "successful": changed, "failed": len(results) - changed, "undoAvailable": changed > 0}
        )

    async def _undo_last(self, session, context, args, todos) -> AgentToolResult:
        now = context.started_at
        change_set = await journal_change_set_repo.find_first_undoable(session, context.user, now)
        if change_set is None:
            return AgentToolResult.failure("NOT_FOUND", "There is no recent journal change to undo.")
        mutations = list(reversed(change_set.mutations))
        for mutation in mutations:
            before = mutation.before_state
            after = mutation.after_state
            entry_id = before["entryId"] if before else after["entryId"]
            entry = await food_entry_repo.find_by_id_and_user(session, entry_id, context.user, include_deleted=True)
            if entry is None:
                continue
            if mutation.action_type == "CREATE":
                entry.mark_deleted(now)
                continue
            self._restore_from(entry, before)
            await food_item_repo.delete_by_entry(session, entry)
            await session.flush()
            for item_snapshot in before.get("items", []):
                session.add(snapshot.recreate_item_for(entry, item_snapshot))
        change_set.mark_undone(now)
        await self.refresh_daily_status(session, context.user, context.chat_id)
        return AgentToolResult.success({"changeSetId": change_set.id, "actions": len(mutations)})

    @staticmethod
    def _restore_from(entry: FoodEntry, before: dict[str, Any]) -> None:
        entry.original_message = before["originalMessage"]
        entry.eaten_at = datetime.fromisoformat(before["eatenAt"])
        entry.calories = before["calories"]
        entry.nutrition_source = before["nutritionSource"]
        entry.confidence = before["confidence"]
        entry.deleted_at = datetime.fromisoformat(before["deletedAt"]) if before.get("deletedAt") else None

    # --- settings / private foods --------------------------------------

    async def _save_private(self, session, context, args, todos) -> AgentToolResult:
        name = _str(args, "name")
        kcal = int(args["caloriesPer100g"]) if args.get("caloriesPer100g") is not None else None
        if not name or kcal is None or kcal < 0 or kcal > 10000:
            return AgentToolResult.failure("VALIDATION_ERROR", "A food name and valid calories per 100 g are required.")
        existing = await private_food_repo.find_by_user_and_name_ignore_case(session, context.user, name)
        if existing is None:
            session.add(PrivateFood(user_id=context.user.id, name=name, calories_per_100g=kcal, created_at=datetime.now(UTC)))
        else:
            existing.calories_per_100g = kcal
        return AgentToolResult.success({"name": name, "caloriesPer100g": kcal})

    async def _update_settings(self, session, context, args, todos) -> AgentToolResult:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        s = await self._settings_for(session, context)
        if "timezone" in args:
            tz = _str(args, "timezone")
            try:
                ZoneInfo(tz)
            except (ZoneInfoNotFoundError, ValueError, KeyError):
                return AgentToolResult.failure("VALIDATION_ERROR", "Use a valid IANA timezone.")
            s.timezone = tz
            # Mirrors continue_onboarding()'s TIMEZONE step: the agent tool is the
            # only path that actually reaches onboarding users in production (see
            # journal_application_service.py's module docstring), so it must drive
            # the same stage transitions or onboarding_completed never becomes true.
            if not s.onboarding_completed and s.onboarding_stage == "TIMEZONE":
                s.require_calorie_target()
        if "calorieTarget" in args and args["calorieTarget"] is not None:
            target = int(args["calorieTarget"])
            if target < 1200 or target > 5000:
                return AgentToolResult.failure("VALIDATION_ERROR", "The calorie target must be 1200-5000.")
            s.calorie_target = target
            if not s.onboarding_completed and s.onboarding_stage == "CALORIE_TARGET":
                s.skip_calorie_target()  # despite the name, this marks the stage complete either way
        elif args.get("skipCalorieTarget") is True and not s.onboarding_completed and s.onboarding_stage == "CALORIE_TARGET":
            s.skip_calorie_target()
        if "reportsEnabled" in args and args["reportsEnabled"] is not None:
            value = str(args["reportsEnabled"]).lower()
            if value not in ("true", "false"):
                return AgentToolResult.failure("VALIDATION_ERROR", "reportsEnabled must be true or false.")
            s.reports_enabled = value == "true"
        if "dayBoundaryHour" in args and args["dayBoundaryHour"] is not None:
            hour = int(args["dayBoundaryHour"])
            if hour < 0 or hour > 23:
                return AgentToolResult.failure("VALIDATION_ERROR", "dayBoundaryHour must be 0-23.")
            s.day_boundary_hour = hour
        if "dayBoundaryReminderEnabled" in args and args["dayBoundaryReminderEnabled"] is not None:
            value = str(args["dayBoundaryReminderEnabled"]).lower()
            if value not in ("true", "false"):
                return AgentToolResult.failure("VALIDATION_ERROR", "dayBoundaryReminderEnabled must be true or false.")
            s.day_boundary_reminder_enabled = value == "true"
        return await self._settings_tool(session, context, args, todos)

    # --- feedback -----------------------------------------------------

    async def _submit_feedback(self, session, context, args, todos) -> AgentToolResult:
        message = _str(args, "message")
        if not message or not message.strip():
            return AgentToolResult.failure("VALIDATION_ERROR", "Feedback text is required.")
        await feedback_repo.create(session, context.user, "ai_detected", message.strip(), datetime.now(UTC))
        return AgentToolResult.success({"recorded": True})

    async def _recent_feedback(self, session, context, args, todos) -> AgentToolResult:
        rows = await feedback_repo.recent(session, context.user)
        return AgentToolResult.success(
            {"feedback": [{"message": row.message, "loggedAt": row.created_at.isoformat()} for row in rows]}
        )

    _HANDLERS: ClassVar[dict[str, Callable]] = {}


JournalToolExecutor._HANDLERS = {
    "get_today_summary": JournalToolExecutor._today,
    "search_entries": JournalToolExecutor._search,
    "get_entry": JournalToolExecutor._entry,
    "get_settings": JournalToolExecutor._settings_tool,
    "resolve_nutrition": JournalToolExecutor._resolve,
    "lookup_food": JournalToolExecutor._resolve,
    "get_private_food": JournalToolExecutor._private_food,
    "search_packaged_food": JournalToolExecutor._packaged_food,
    "get_pending_nutrition_quotes": JournalToolExecutor._pending_quotes,
    "select_packaged_food": JournalToolExecutor._select_packaged,
    "search_web": JournalToolExecutor._search_web,
    "fetch_web_page": JournalToolExecutor._fetch_web_page,
    "estimate_food": JournalToolExecutor._estimate_food,
    "apply_journal_actions": JournalToolExecutor._apply_actions,
    "undo_last_change": JournalToolExecutor._undo_last,
    "plan_todos": JournalToolExecutor._plan_todos,
    "complete_todo": JournalToolExecutor._complete_todo,
    "save_private_food": JournalToolExecutor._save_private,
    "update_settings": JournalToolExecutor._update_settings,
    "submit_feedback": JournalToolExecutor._submit_feedback,
    "get_recent_feedback": JournalToolExecutor._recent_feedback,
}
