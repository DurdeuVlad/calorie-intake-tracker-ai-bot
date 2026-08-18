from dataclasses import dataclass


@dataclass(frozen=True)
class MealItem:
    name: str | None
    grams: float | None
    total_calories: int | None = None
    calories_per_100g: int | None = None
    protein_grams: float | None = None
    carbs_grams: float | None = None
    fat_grams: float | None = None
    barcode: str | None = None
