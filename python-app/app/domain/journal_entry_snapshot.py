"""Immutable journal state captured before/after one mutation, stored as JSONB.

The dict keys here MUST stay exact camelCase matching JournalEntrySnapshot.java
(entryId, originalMessage, eatenAt, calories, nutritionSource, confidence,
deletedAt, items[itemId, name, quantity, quantityUnit, quantityGrams, calories,
proteinGrams, carbsGrams, fatGrams, nutritionSource, nutritionConfidence,
optional nutritionEvidence]) -- existing rows in the shared database were written
with these exact key names."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.db.models.entries import FoodEntry, FoodItem
from app.db.models.nutrition import NutritionEvidence
from app.domain.quantity_unit import QuantityUnit


def _dec(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def capture_evidence(evidence: NutritionEvidence) -> dict[str, Any]:
    return {
        "evidenceId": str(evidence.evidence_id),
        "selectedQuoteId": str(evidence.selected_quote_id) if evidence.selected_quote_id else None,
        "provider": evidence.provider,
        "sourceName": evidence.source_name,
        "sourceUrl": evidence.source_url,
        "sourceQuery": evidence.source_query,
        "selectedCandidate": evidence.selected_candidate,
        "quantityGrams": _dec(evidence.quantity_grams),
        "caloriesPer100g": evidence.calories_per_100g,
        "totalCalories": evidence.total_calories,
        "derivation": evidence.derivation,
        "confidence": evidence.confidence,
        "sourceFetchedAt": evidence.source_fetched_at.isoformat() if evidence.source_fetched_at else None,
        "sourceCacheHit": evidence.source_cache_hit,
        "capturedAt": evidence.captured_at.isoformat(),
    }


def capture_item(
    item: FoodItem,
    evidence: NutritionEvidence | None = None,
    *,
    include_evidence: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "itemId": item.id,
        "name": item.name,
        "quantity": _dec(item.quantity),
        "quantityUnit": item.quantity_unit,
        "quantityGrams": _dec(item.quantity_grams),
        "calories": item.calories,
        "proteinGrams": _dec(item.protein_grams),
        "carbsGrams": _dec(item.carbs_grams),
        "fatGrams": _dec(item.fat_grams),
        "nutritionSource": item.nutrition_source,
        "nutritionConfidence": item.nutrition_confidence,
    }
    if include_evidence:
        result["nutritionEvidence"] = [capture_evidence(evidence)] if evidence is not None else []
    return result


def capture(
    entry: FoodEntry,
    items: list[FoodItem],
    evidence_by_item_id: dict[int, NutritionEvidence] | None = None,
) -> dict[str, Any]:
    if entry is None:
        raise ValueError("Entry is required")
    return {
        "entryId": entry.id,
        "originalMessage": entry.original_message,
        "eatenAt": entry.eaten_at.isoformat() if entry.eaten_at else None,
        "calories": entry.calories,
        "nutritionSource": entry.nutrition_source,
        "confidence": entry.confidence,
        "deletedAt": entry.deleted_at.isoformat() if entry.deleted_at else None,
        "items": [
            capture_item(
                i,
                (evidence_by_item_id or {}).get(i.id),
                include_evidence=evidence_by_item_id is not None,
            )
            for i in items
        ],
    }


def recreate_item_for(entry: FoodEntry, snapshot: dict[str, Any]) -> FoodItem:
    quantity = snapshot.get("quantity")
    quantity_grams = snapshot.get("quantityGrams")
    effective_quantity = quantity if quantity is not None else quantity_grams
    unit = snapshot.get("quantityUnit")
    effective_unit = unit if unit else (QuantityUnit.UNSPECIFIED.value if quantity_grams is None else QuantityUnit.G.value)
    quantity_value = Decimal(str(effective_quantity)) if effective_quantity is not None else None
    quantity_grams_value = (
        Decimal(str(quantity_grams))
        if quantity_grams is not None
        else quantity_value if effective_unit == QuantityUnit.G.value else None
    )
    return FoodItem(
        entry_id=entry.id,
        name=snapshot["name"],
        quantity_grams=quantity_grams_value,
        quantity=quantity_value,
        quantity_unit=effective_unit,
        calories=snapshot.get("calories"),
        protein_grams=Decimal(str(snapshot["proteinGrams"])) if snapshot.get("proteinGrams") is not None else None,
        carbs_grams=Decimal(str(snapshot["carbsGrams"])) if snapshot.get("carbsGrams") is not None else None,
        fat_grams=Decimal(str(snapshot["fatGrams"])) if snapshot.get("fatGrams") is not None else None,
        nutrition_source=snapshot.get("nutritionSource") or "manual",
        nutrition_confidence=snapshot.get("nutritionConfidence") or "unknown",
    )


def recreate_evidence_for(entry: FoodEntry, item: FoodItem, item_snapshot: dict[str, Any]) -> list[NutritionEvidence]:
    raw_evidence = item_snapshot.get("nutritionEvidence", [])
    if not isinstance(raw_evidence, list):
        raise TypeError("Nutrition evidence snapshot must be a list")

    restored: list[NutritionEvidence] = []
    for raw in raw_evidence:
        if not isinstance(raw, dict):
            raise TypeError("Nutrition evidence snapshot item must be an object")
        restored.append(
            NutritionEvidence(
                evidence_id=UUID(str(raw["evidenceId"])),
                food_entry_id=entry.id,
                food_item_id=item.id,
                selected_quote_id=UUID(str(raw["selectedQuoteId"])) if raw.get("selectedQuoteId") else None,
                provider=raw["provider"],
                source_name=raw["sourceName"],
                source_url=raw.get("sourceUrl"),
                source_query=raw.get("sourceQuery"),
                selected_candidate=raw["selectedCandidate"],
                quantity_grams=Decimal(str(raw["quantityGrams"])),
                calories_per_100g=raw["caloriesPer100g"],
                total_calories=raw["totalCalories"],
                derivation=raw["derivation"],
                confidence=raw["confidence"],
                source_fetched_at=datetime.fromisoformat(raw["sourceFetchedAt"]) if raw.get("sourceFetchedAt") else None,
                source_cache_hit=raw.get("sourceCacheHit", False),
                captured_at=datetime.fromisoformat(raw["capturedAt"]),
            )
        )
    return restored
