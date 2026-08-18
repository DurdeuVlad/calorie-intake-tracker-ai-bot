"""Nutrition resolution priority, ported verbatim from CachedNutritionResolver.java:
1. item.grams is missing/<=0 -> unresolved, source "manual".
2. item.calories_per_100g explicitly declared -> compute total, source "manual".
3. item.barcode present -> 30-day cache, else live OpenFoodFacts lookup (cached on hit), source "open_food_facts".
4. Otherwise -> user's saved private foods (case-insensitive name match), source "private_food".
5. Otherwise -> item unchanged, source "manual" (unresolved).
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import NutritionSourceCache
from app.db.models.users import FoodUser
from app.domain.journal_intent import MealItem
from app.integrations.openfoodfacts_types import NutritionProfile, OpenFoodFactsClient
from app.repositories import nutrition_source_cache_repo, private_food_repo

CACHE_TTL = timedelta(days=30)


@dataclass(frozen=True)
class ResolvedMealItem:
    item: MealItem
    source: str


def _round(value: int | None, factor: float) -> int | None:
    return round(value * factor) if value is not None else None


def _scale(value: float | None, factor: float) -> float | None:
    return value * factor if value is not None else None


def _cache_to_profile(cache: NutritionSourceCache) -> NutritionProfile:
    return NutritionProfile(
        name=cache.product_name,
        calories_per_100g=cache.calories_per_100g,
        protein_per_100g=float(cache.protein_per_100g) if cache.protein_per_100g is not None else None,
        carbs_per_100g=float(cache.carbs_per_100g) if cache.carbs_per_100g is not None else None,
        fat_per_100g=float(cache.fat_per_100g) if cache.fat_per_100g is not None else None,
        source="open_food_facts",
        source_url=cache.source_url,
    )


def _scale_item(item: MealItem, profile: NutritionProfile) -> MealItem:
    factor = item.grams / 100.0
    return replace(
        item,
        name=profile.name,
        total_calories=_round(profile.calories_per_100g, factor),
        calories_per_100g=profile.calories_per_100g,
        protein_grams=_scale(profile.protein_per_100g, factor),
        carbs_grams=_scale(profile.carbs_per_100g, factor),
        fat_grams=_scale(profile.fat_per_100g, factor),
    )


async def resolve(
    session: AsyncSession, user: FoodUser, item: MealItem | None, off: OpenFoodFactsClient
) -> ResolvedMealItem:
    if item is None or item.grams is None or item.grams <= 0:
        return ResolvedMealItem(item, "manual")

    if item.calories_per_100g is not None:
        factor = item.grams / 100.0
        return ResolvedMealItem(replace(item, total_calories=_round(item.calories_per_100g, factor)), "manual")

    if item.barcode is not None:
        now = datetime.now(timezone.utc)
        existing = await nutrition_source_cache_repo.find_by_barcode(session, item.barcode)
        profile: NutritionProfile | None = None
        if existing is not None and existing.fetched_at > now - CACHE_TTL:
            profile = _cache_to_profile(existing)
        else:
            fetched = await off.by_barcode(item.barcode)
            if fetched is not None:
                profile = fetched
                if existing is None:
                    session.add(
                        NutritionSourceCache(
                            barcode=item.barcode,
                            product_name=fetched.name,
                            calories_per_100g=fetched.calories_per_100g,
                            protein_per_100g=fetched.protein_per_100g,
                            carbs_per_100g=fetched.carbs_per_100g,
                            fat_per_100g=fetched.fat_per_100g,
                            source_url=fetched.source_url or "",
                            fetched_at=now,
                        )
                    )
                else:
                    existing.product_name = fetched.name
                    existing.calories_per_100g = fetched.calories_per_100g
                    existing.protein_per_100g = fetched.protein_per_100g
                    existing.carbs_per_100g = fetched.carbs_per_100g
                    existing.fat_per_100g = fetched.fat_per_100g
                    existing.source_url = fetched.source_url or ""
                    existing.fetched_at = now
        if profile is not None:
            return ResolvedMealItem(_scale_item(item, profile), "open_food_facts")

    private = await private_food_repo.find_by_user_and_name_ignore_case(session, user, item.name)
    if private is not None:
        profile = NutritionProfile(
            name=private.name,
            calories_per_100g=private.calories_per_100g,
            protein_per_100g=float(private.protein_per_100g) if private.protein_per_100g is not None else None,
            carbs_per_100g=float(private.carbs_per_100g) if private.carbs_per_100g is not None else None,
            fat_per_100g=float(private.fat_per_100g) if private.fat_per_100g is not None else None,
            source="private_food",
            source_url=None,
        )
        return ResolvedMealItem(_scale_item(item, profile), "private_food")

    return ResolvedMealItem(item, "manual")
