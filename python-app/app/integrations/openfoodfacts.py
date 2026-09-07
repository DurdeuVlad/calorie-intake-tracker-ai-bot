"""OpenFoodFacts client, ported from OpenFoodFactsClient.java. Barcode lookup
and fuzzy name/brand search with exact-match-then-token-overlap ranking."""

import math
import re
import unicodedata
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.db.constraints import MAX_CALORIES_PER_100G, MIN_CALORIES_PER_100G
from app.integrations.http_response import request_bounded_json
from app.integrations.openfoodfacts_types import (
    NutritionProfile,
    OpenFoodFactsUnavailable,
    PackagedFoodResult,
    validate_nutrition_profile,
    validate_packaged_food_result,
)

_BARCODE_RE = re.compile(r"\d{8,14}")
_USER_AGENT = "food-tracker-telegram-bot/2.0"


def _normalized(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFD", value)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(
        "".join(char.lower() if char.isalnum() else " " for char in without_marks).split()
    )


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
            base_url=settings.open_food_facts_base_url,
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0),
            headers={"User-Agent": _USER_AGENT},
            trust_env=False,
        )

    async def by_barcode(self, barcode: str) -> NutritionProfile | None:
        if not barcode or not _BARCODE_RE.fullmatch(barcode):
            return None
        try:
            payload = await request_bounded_json(
                self._http,
                "GET",
                f"/product/{barcode}",
                params={"fields": "code,product_name,nutriments"},
            )
            product = payload.get("product") or {}
            nutrients = product.get("nutriments") or {}
            product_name = product.get("product_name")
            if payload.get("status") != 1 or not isinstance(product_name, str) or not product_name.strip():
                return None
            calories = self._integer(nutrients, "energy-kcal_100g")
            if calories is None:
                return None
            return validate_nutrition_profile(
                NutritionProfile(
                    name=product_name,
                    calories_per_100g=calories,
                    protein_per_100g=self._number(nutrients, "proteins_100g"),
                    carbs_per_100g=self._number(nutrients, "carbohydrates_100g"),
                    fat_per_100g=self._number(nutrients, "fat_100g"),
                    source="open_food_facts",
                    source_url=f"https://world.openfoodfacts.org/product/{barcode}",
                )
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
            payload = await request_bounded_json(
                self._http,
                "GET",
                "/cgi/search.pl",
                params={
                    "search_terms": terms,
                    "json": 1,
                    "fields": "code,product_name,brands,nutriments",
                    "page_size": 20,
                },
            )
            products = payload.get("products") if isinstance(payload, dict) else None
            if not isinstance(products, list):
                return []

            matches: list[_Ranked] = []
            for source_order, product in enumerate(products):
                if not isinstance(product, dict):
                    continue
                raw_barcode = product.get("code")
                barcode = str(raw_barcode) if isinstance(raw_barcode, (str, int)) and not isinstance(raw_barcode, bool) else None
                product_name = product.get("product_name")
                product_brand = product.get("brands")
                if barcode is None or not isinstance(product_name, str):
                    continue
                product_brand = product_brand if isinstance(product_brand, str) else ""
                calories = self._integer(product.get("nutriments") or {}, "energy-kcal_100g")
                if (
                    not _BARCODE_RE.fullmatch(barcode)
                    or not product_name.strip()
                    or calories is None
                    or not MIN_CALORIES_PER_100G <= calories <= MAX_CALORIES_PER_100G
                ):
                    continue
                exact = 1 if _exact_match(name, brand, product_name, product_brand) else 0
                overlap = _token_overlap(terms, f"{product_name} {product_brand}")
                try:
                    result = validate_packaged_food_result(
                        PackagedFoodResult(
                            product_name=product_name,
                            brand=product_brand or None,
                            calories_per_100g=calories,
                            barcode=barcode,
                            source_url=f"https://world.openfoodfacts.org/product/{barcode}",
                            match_quality="EXACT" if exact else "PARTIAL",
                        )
                    )
                except ValueError:
                    continue
                matches.append(_Ranked(result, exact, overlap, source_order))
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
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        try:
            result = float(value)
        except (OverflowError, ValueError):
            return None
        return result if math.isfinite(result) else None

    @staticmethod
    def _integer(root: dict, field: str) -> int | None:
        value = OpenFoodFactsHttpClient._number(root, field)
        return round(value) if value is not None else None

    async def close(self) -> None:
        await self._http.aclose()
