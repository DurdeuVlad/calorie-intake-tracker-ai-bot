"""Shared types for the OpenFoodFacts integration. The real HTTP-backed client
is added in Phase 6; a null client that always misses is used until then so
the nutrition resolver's barcode-lookup branch can be fully wired now."""

import math
import re
from dataclasses import dataclass, replace
from typing import Protocol

from app.db.constraints import (
    MAX_BARCODE_CHARS,
    MAX_CALORIES_PER_100G,
    MAX_TEXT_CHARS,
    MAX_URL_CHARS,
    MIN_CALORIES_PER_100G,
)

_BARCODE_RE = re.compile(r"\d{8,14}")


def _external_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > limit:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    return value


def _external_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except (OverflowError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


class OpenFoodFactsUnavailable(RuntimeError):
    """The provider could not answer safely; callers should use cached data."""

    def __init__(self, message: str, *, rate_limited: bool = False) -> None:
        super().__init__(message)
        self.rate_limited = rate_limited


@dataclass(frozen=True)
class NutritionProfile:
    name: str
    calories_per_100g: int | None
    protein_per_100g: float | None
    carbs_per_100g: float | None
    fat_per_100g: float | None
    source: str
    source_url: str | None


@dataclass(frozen=True)
class PackagedFoodResult:
    product_name: str
    brand: str | None
    calories_per_100g: int
    barcode: str
    source_url: str
    match_quality: str  # "EXACT" | "PARTIAL"


def validate_nutrition_profile(value: NutritionProfile) -> NutritionProfile:
    name = _external_text(value.name, MAX_TEXT_CHARS)
    source = _external_text(value.source, MAX_TEXT_CHARS)
    source_url = _external_text(value.source_url, MAX_URL_CHARS)
    calories = value.calories_per_100g
    if (
        name is None
        or source is None
        or isinstance(calories, bool)
        or not isinstance(calories, int)
        or not MIN_CALORIES_PER_100G <= calories <= MAX_CALORIES_PER_100G
    ):
        raise ValueError("Open Food Facts returned invalid nutrition profile data")
    macros = {
        "protein_per_100g": _external_number(value.protein_per_100g),
        "carbs_per_100g": _external_number(value.carbs_per_100g),
        "fat_per_100g": _external_number(value.fat_per_100g),
    }
    for field, raw in (
        ("protein_per_100g", value.protein_per_100g),
        ("carbs_per_100g", value.carbs_per_100g),
        ("fat_per_100g", value.fat_per_100g),
    ):
        if raw is not None and macros[field] is None:
            raise ValueError(f"Open Food Facts returned invalid {field}")
    return replace(
        value,
        name=name,
        source=source,
        source_url=source_url,
        **macros,
    )


def validate_packaged_food_result(value: PackagedFoodResult) -> PackagedFoodResult:
    product_name = _external_text(value.product_name, MAX_TEXT_CHARS)
    brand = _external_text(value.brand, MAX_TEXT_CHARS)
    source_url = _external_text(value.source_url, MAX_URL_CHARS)
    if (
        product_name is None
        or source_url is None
        or not isinstance(value.barcode, str)
        or len(value.barcode) > MAX_BARCODE_CHARS
        or _BARCODE_RE.fullmatch(value.barcode) is None
        or isinstance(value.calories_per_100g, bool)
        or not isinstance(value.calories_per_100g, int)
        or not MIN_CALORIES_PER_100G <= value.calories_per_100g <= MAX_CALORIES_PER_100G
        or value.match_quality not in {"EXACT", "PARTIAL"}
    ):
        raise ValueError("Open Food Facts returned invalid packaged-food data")
    return replace(value, product_name=product_name, brand=brand, source_url=source_url)


class OpenFoodFactsClient(Protocol):
    async def by_barcode(self, barcode: str) -> NutritionProfile | None: ...

    async def search_by_name(self, name: str, brand: str | None) -> list[PackagedFoodResult]: ...


class NullOpenFoodFactsClient:
    """Always misses. Used until Phase 6 wires the real HTTP client."""

    async def by_barcode(self, barcode: str) -> NutritionProfile | None:
        return None

    async def search_by_name(self, name: str, brand: str | None) -> list[PackagedFoodResult]:
        return []
