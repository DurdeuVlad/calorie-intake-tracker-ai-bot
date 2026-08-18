"""Immutable journal state captured before/after one mutation, stored as JSONB.

The dict keys here MUST stay exact camelCase matching JournalEntrySnapshot.java
(entryId, originalMessage, eatenAt, calories, nutritionSource, confidence,
deletedAt, items[itemId, name, quantity, quantityUnit, quantityGrams, calories,
proteinGrams, carbsGrams, fatGrams, nutritionSource, nutritionConfidence]) --
existing rows in the shared database were written with these exact key names."""

from decimal import Decimal
from typing import Any

from app.db.models.entries import FoodEntry, FoodItem
from app.domain.quantity_unit import QuantityUnit


def _dec(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def capture_item(item: FoodItem) -> dict[str, Any]:
    return {
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


def capture(entry: FoodEntry, items: list[FoodItem]) -> dict[str, Any]:
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
        "items": [capture_item(i) for i in items],
    }


def recreate_item_for(entry: FoodEntry, snapshot: dict[str, Any]) -> FoodItem:
    quantity = snapshot.get("quantity")
    quantity_grams = snapshot.get("quantityGrams")
    effective_quantity = quantity if quantity is not None else quantity_grams
    unit = snapshot.get("quantityUnit")
    effective_unit = unit if unit else (QuantityUnit.UNSPECIFIED.value if quantity_grams is None else QuantityUnit.G.value)
    return FoodItem(
        entry_id=entry.id,
        name=snapshot["name"],
        quantity=Decimal(str(effective_quantity)) if effective_quantity is not None else None,
        quantity_unit=effective_unit,
        calories=snapshot.get("calories"),
        protein_grams=Decimal(str(snapshot["proteinGrams"])) if snapshot.get("proteinGrams") is not None else None,
        carbs_grams=Decimal(str(snapshot["carbsGrams"])) if snapshot.get("carbsGrams") is not None else None,
        fat_grams=Decimal(str(snapshot["fatGrams"])) if snapshot.get("fatGrams") is not None else None,
        nutrition_source=snapshot.get("nutritionSource") or "manual",
        nutrition_confidence=snapshot.get("nutritionConfidence") or "unknown",
    )
