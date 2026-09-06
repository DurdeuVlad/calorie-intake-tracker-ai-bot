"""Shared helpers, constants, and validation utilities for tool modules.

Extracted from journal_tool_executor.py as part of the v2.0 tool module split
(issue #105). These are pure functions and constants with no side effects."""

import re
import uuid
from datetime import UTC, datetime, time, timedelta
from datetime import date as date_type
from typing import Any

from app.db.models.entries import FoodEntry
from app.domain.agent_types import AgentContext
from app.domain.journal_intent import MealItem
from app.domain.quantity_unit import QuantityUnit

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
    roundtrip = aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    if roundtrip != local_naive:
        raise ValidationError("That local time does not exist because of daylight-saving time. Use another time.")

    result = aware.astimezone(UTC)
    if result > base:
        raise ValidationError("Future meal times are not allowed.")
    return result
