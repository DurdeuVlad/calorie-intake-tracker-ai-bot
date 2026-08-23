"""Shared types for the OpenFoodFacts integration. The real HTTP-backed client
is added in Phase 6; a null client that always misses is used until then so
the nutrition resolver's barcode-lookup branch can be fully wired now."""

from dataclasses import dataclass
from typing import Protocol


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


class OpenFoodFactsClient(Protocol):
    async def by_barcode(self, barcode: str) -> NutritionProfile | None: ...

    async def search_by_name(self, name: str, brand: str | None) -> list[PackagedFoodResult]: ...


class NullOpenFoodFactsClient:
    """Always misses. Used until Phase 6 wires the real HTTP client."""

    async def by_barcode(self, barcode: str) -> NutritionProfile | None:
        return None

    async def search_by_name(self, name: str, brand: str | None) -> list[PackagedFoodResult]:
        return []
