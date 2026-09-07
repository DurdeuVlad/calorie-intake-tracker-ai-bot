"""Preflight checks for the persisted data-boundary migration.

Run this before upgrading a deployment to the data-boundary revision. The
migration intentionally does not silently cap or delete user journal data;
operators must remediate any reported rows before adding the CHECK constraints.
"""

import asyncio

from sqlalchemy import text

from app.db.base import get_engine

_CHECKS = (
    (
        "food_entries.calories",
        "SELECT count(*) FROM food_entries WHERE calories IS NOT NULL AND (calories < 0 OR calories > 10000)",
    ),
    (
        "food_items.calories",
        "SELECT count(*) FROM food_items WHERE calories IS NOT NULL AND (calories < 0 OR calories > 10000)",
    ),
    (
        "food_items.quantity",
        "SELECT count(*) FROM food_items WHERE quantity IS NOT NULL AND (quantity <= 0 OR quantity > 100000.00)",
    ),
    (
        "food_items.quantity_grams",
        "SELECT count(*) FROM food_items WHERE quantity_grams IS NOT NULL AND (quantity_grams <= 0 OR quantity_grams > 100000.00)",
    ),
    (
        "private_foods.calories_per_100g",
        "SELECT count(*) FROM private_foods WHERE calories_per_100g IS NOT NULL AND (calories_per_100g < 0 OR calories_per_100g > 10000)",
    ),
    (
        "nutrition_source_cache.calories_per_100g",
        "SELECT count(*) FROM nutrition_source_cache WHERE calories_per_100g IS NOT NULL AND (calories_per_100g < 0 OR calories_per_100g > 10000)",
    ),
    (
        "pending_nutrition_quotes.grams",
        "SELECT count(*) FROM pending_nutrition_quotes WHERE grams <= 0 OR grams > 100000.00",
    ),
    (
        "pending_nutrition_quotes.calories_per_100g",
        "SELECT count(*) FROM pending_nutrition_quotes WHERE calories_per_100g < 1 OR calories_per_100g > 10000",
    ),
    (
        "nutrition_evidence.quantity_grams",
        "SELECT count(*) FROM nutrition_evidence WHERE quantity_grams <= 0 OR quantity_grams > 100000.00",
    ),
    (
        "nutrition_evidence.calories_per_100g",
        "SELECT count(*) FROM nutrition_evidence WHERE calories_per_100g < 1 OR calories_per_100g > 10000",
    ),
    (
        "nutrition_evidence.total_calories",
        "SELECT count(*) FROM nutrition_evidence WHERE total_calories < 0 OR total_calories > 10000",
    ),
    (
        "user_settings.calorie_target",
        "SELECT count(*) FROM user_settings WHERE calorie_target IS NOT NULL AND (calorie_target < 1200 OR calorie_target > 5000)",
    ),
)


async def invalid_rows() -> list[tuple[str, int]]:
    engine = get_engine()
    async with engine.connect() as connection:
        invalid: list[tuple[str, int]] = []
        for label, query in _CHECKS:
            count = int((await connection.execute(text(query))).scalar_one())
            if count:
                invalid.append((label, count))
        return invalid


async def main() -> None:
    invalid = await invalid_rows()
    if invalid:
        details = "\n".join(f"- {label}: {count} row(s)" for label, count in invalid)
        raise RuntimeError(
            "Data-boundary migration preflight failed. Remediate these rows before running Alembic:\n" + details
        )
    print("Data-boundary migration preflight passed: no out-of-range rows found.")


if __name__ == "__main__":
    asyncio.run(main())
