"""OpenFoodFacts client, ported from OpenFoodFactsClient.java. Barcode lookup
and fuzzy name/brand search with exact-match-then-token-overlap ranking."""

import re
import unicodedata
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.integrations.openfoodfacts_types import (
    NutritionProfile,
    OpenFoodFactsUnavailable,
    PackagedFoodResult,
)

_BARCODE_RE = re.compile(r"\d{8,14}")


def _normalized(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFD", value)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = without_marks.lower()
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def _exact_match(name: str, requested_brand: str | None, product_name: str, product_brand: str) -> bool:
    if _normalized(name) == _normalized(product_name):
        return True
    return bool(requested_brand) and _normalized(requested_brand) == _normalized(product_brand)


def _token_overlap(query: str, candidate: str) -> int:
    tokens = [t for t in _normalized(query).split(" ") if t]
    normalized_candidate = _normalized(candidate)
    return sum(1 for token in tokens if token in normalized_candidate)


@dataclass
class _Ranked:
    result: PackagedFoodResult
    exact: int
    overlap: int
    source_order: int


class OpenFoodFactsHttpClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self._http = http or httpx.AsyncClient(
            base_url=settings.open_food_facts_base_url, timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
        )

    async def by_barcode(self, barcode: str) -> NutritionProfile | None:
        if not barcode or not _BARCODE_RE.fullmatch(barcode):
            return None
        try:
            response = await self._http.get(f"/product/{barcode}", params={"fields": "code,product_name,nutriments"})
            response.raise_for_status()
            payload = response.json()
            product = payload.get("product") or {}
            nutrients = product.get("nutriments") or {}
            if payload.get("status") != 1 or not (product.get("product_name") or "").strip():
                return None
            calories = self._integer(nutrients, "energy-kcal_100g")
            if calories is None:
                return None
            return NutritionProfile(
                name=product["product_name"],
                calories_per_100g=calories,
                protein_per_100g=self._number(nutrients, "proteins_100g"),
                carbs_per_100g=self._number(nutrients, "carbohydrates_100g"),
                fat_per_100g=self._number(nutrients, "fat_100g"),
                source="open_food_facts",
                source_url=f"https://world.openfoodfacts.org/product/{barcode}",
            )
        except httpx.HTTPStatusError as error:
            raise OpenFoodFactsUnavailable("Open Food Facts rejected the barcode lookup.", rate_limited=error.response.status_code == 429) from error
        except httpx.HTTPError as error:
            raise OpenFoodFactsUnavailable("Open Food Facts is unavailable.") from error
        except Exception as error:  # malformed provider response is not a nutrition miss
            raise OpenFoodFactsUnavailable("Open Food Facts returned an unusable response.") from error

    async def search_by_name(self, name: str, brand: str | None) -> list[PackagedFoodResult]:
        if not name or not name.strip():
            return []
        try:
            terms = f"{name} {brand}" if brand and brand.strip() else name
            response = await self._http.get(
                "/search", params={"search_terms": terms, "fields": "code,product_name,brands,nutriments", "page_size": 20}
            )
            response.raise_for_status()
            products = response.json().get("products")
            if not isinstance(products, list):
                return []

            matches: list[_Ranked] = []
            for source_order, product in enumerate(products):
                barcode = str(product.get("code", ""))
                product_name = str(product.get("product_name", "")).strip()
                product_brand = str(product.get("brands", "")).strip()
                calories = self._integer(product.get("nutriments") or {}, "energy-kcal_100g")
                if not _BARCODE_RE.fullmatch(barcode) or not product_name or calories is None or not (1 <= calories <= 2000):
                    continue
                exact = 1 if _exact_match(name, brand, product_name, product_brand) else 0
                overlap = _token_overlap(terms, f"{product_name} {product_brand}")
                matches.append(
                    _Ranked(
                        PackagedFoodResult(
                            product_name=product_name, brand=product_brand or None, calories_per_100g=calories,
                            barcode=barcode, source_url=f"https://world.openfoodfacts.org/product/{barcode}",
                            match_quality="EXACT" if exact else "PARTIAL",
                        ),
                        exact, overlap, source_order,
                    )
                )
            matches.sort(key=lambda m: (-m.exact, -m.overlap, m.source_order))
            return [m.result for m in matches[:5]]
        except httpx.HTTPStatusError as error:
            raise OpenFoodFactsUnavailable("Open Food Facts rejected the packaged-food lookup.", rate_limited=error.response.status_code == 429) from error
        except httpx.HTTPError as error:
            raise OpenFoodFactsUnavailable("Open Food Facts is unavailable.") from error
        except Exception as error:  # malformed provider response is not a nutrition miss
            raise OpenFoodFactsUnavailable("Open Food Facts returned an unusable response.") from error

    @staticmethod
    def _number(root: dict, field: str) -> float | None:
        value = root.get(field)
        return float(value) if isinstance(value, (int, float)) else None

    @staticmethod
    def _integer(root: dict, field: str) -> int | None:
        value = OpenFoodFactsHttpClient._number(root, field)
        return round(value) if value is not None else None

    async def close(self) -> None:
        await self._http.aclose()
