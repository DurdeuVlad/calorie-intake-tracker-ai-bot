"""Shared helpers, constants, and validation utilities for tool modules.

Extracted from journal_tool_executor.py as part of the v2.0 tool module split
(issue #105). These are pure functions and constants with no side effects."""

import math
import re
import uuid
from datetime import UTC, datetime, time, timedelta
from datetime import date as date_type
from decimal import Decimal, InvalidOperation
from typing import Any

from app.db.constraints import (
    CALORIES_REFERENCE_GRAMS,
    MAX_BARCODE_CHARS,
    MAX_BIGINT,
    MAX_CALORIES,
    MAX_CALORIES_PER_100G,
    MAX_IDENTIFIER_CHARS,
    MAX_QUANTITY,
    MAX_TEXT_CHARS,
    MIN_CALORIES,
    MIN_CALORIES_PER_100G,
    MIN_QUANTITY,
    QUANTITY_STEP,
)
from app.db.models.entries import FoodEntry
from app.domain.agent_types import AgentContext
from app.domain.journal_intent import MealItem
from app.domain.quantity_unit import QuantityUnit

MAX_DATABASE_ID = MAX_BIGINT
MAX_GRAMS = float(MAX_QUANTITY)
MAX_TOTAL_CALORIES = MAX_CALORIES
WEB_SEARCH_CACHE_TTL = timedelta(days=1)
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
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{key} must be text")
    return value


def _validate_text(value: object, key: str, limit: int) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{key} must be text")
    if len(value) > limit:
        raise ValidationError(f"{key} must be at most {limit} characters")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValidationError(f"{key} contains unsupported control characters")
    return value


def _text(args: dict, key: str, limit: int) -> str | None:
    value = _str(args, key)
    return None if value is None else _validate_text(value, key, limit)


def _bounded_text(value: object, limit: int) -> str:
    text = str(value)
    return "".join(char for char in text if ord(char) >= 32 and ord(char) != 127)[:limit]


def _optional_int(args: dict, key: str, min_value: int | None = None, max_value: int | None = None) -> int | None:
    value = args.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{key} must be an integer")
    if min_value is not None and value < min_value:
        raise ValidationError(f"{key} must be at least {min_value}")
    if max_value is not None and value > max_value:
        raise ValidationError(f"{key} must be at most {max_value}")
    return value


def _int_required(args: dict, key: str, min_value: int | None = None, max_value: int | None = None) -> int:
    value = _optional_int(args, key, min_value, max_value)
    if value is None:
        raise ValidationError(f"{key} is required")
    return value


def _decimal_number(
    args: dict,
    key: str,
    min_value: float | None = None,
    max_value: float | None = None,
    exclusive_min_value: float | None = None,
) -> float | None:
    value = args.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{key} must be a number")
    try:
        result = float(value)
    except OverflowError as failure:
        raise ValidationError(f"{key} must be finite") from failure
    if not math.isfinite(result):
        raise ValidationError(f"{key} must be finite")
    if min_value is not None and result < min_value:
        raise ValidationError(f"{key} must be at least {min_value}")
    if exclusive_min_value is not None and result <= exclusive_min_value:
        raise ValidationError(f"{key} must be greater than {exclusive_min_value}")
    if max_value is not None and result > max_value:
        raise ValidationError(f"{key} must be at most {max_value}")
    return result


def _quantity_number(
    args: dict,
    key: str,
    min_value: float = float(MIN_QUANTITY),
    max_value: float = MAX_GRAMS,
) -> float | None:
    value = _decimal_number(
        args, key, min_value=min_value, max_value=max_value, exclusive_min_value=float(MIN_QUANTITY)
    )
    if value is None:
        return None
    try:
        decimal_value = Decimal(str(value))
        if decimal_value.quantize(QUANTITY_STEP) != decimal_value:
            raise ValidationError(f"{key} must have at most two decimal places")
    except InvalidOperation as failure:
        raise ValidationError(f"{key} must be a valid quantity") from failure
    return value


def _quote_id(args: dict) -> uuid.UUID | None:
    raw = _text(args, "quoteId", MAX_IDENTIFIER_CHARS)
    if raw is None:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def _derived_calories(grams: float, calories_per_100g: int) -> int:
    return round(float(grams) * calories_per_100g / float(CALORIES_REFERENCE_GRAMS))


def _meal_item(args: dict) -> MealItem:
    return MealItem(
        name=_text(args, "name", MAX_TEXT_CHARS),
        grams=_quantity_number(args, "grams"),
        total_calories=_optional_int(args, "totalCalories", min_value=MIN_CALORIES, max_value=MAX_CALORIES),
        calories_per_100g=_optional_int(
            args, "caloriesPer100g", min_value=MIN_CALORIES_PER_100G, max_value=MAX_CALORIES_PER_100G
        ),
        barcode=_text(args, "barcode", MAX_BARCODE_CHARS),
    )


def _valid_item(item: MealItem | None) -> bool:
    return item is not None and bool(item.name and item.name.strip()) and item.grams is not None and item.grams > 0


def _valid_calories_per_100g(value: int | None) -> bool:
    return value is not None and MIN_CALORIES_PER_100G <= value <= MAX_CALORIES_PER_100G


def _quantity_unit(raw: str | None, quantity: float | None) -> str:
    if not raw:
        return QuantityUnit.UNSPECIFIED.value if quantity is None else QuantityUnit.PORTION.value
    try:
        unit = QuantityUnit.from_database_value(raw).value
    except ValueError as failure:
        raise ValidationError("Use g, ml, portion, or unspecified for the unit.") from failure
    if quantity is None and unit != QuantityUnit.UNSPECIFIED.value:
        raise ValidationError("A quantity is required when a concrete unit is provided.")
    return unit


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
