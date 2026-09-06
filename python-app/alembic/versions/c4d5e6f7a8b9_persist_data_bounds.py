"""Enforce canonical business bounds at the database boundary."""

from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

MIN_CALORIES = 0
MAX_CALORIES = 10000
MIN_CALORIES_PER_100G = 1
MAX_CALORIES_PER_100G = 10000
MIN_CALORIE_TARGET = 1200
MAX_CALORIE_TARGET = 5000
MAX_QUANTITY = "100000.00"

_CONSTRAINTS = (
    (
        "food_entries",
        "ck_food_entries_calories_range",
        f"calories IS NULL OR (calories >= {MIN_CALORIES} AND calories <= {MAX_CALORIES})",
    ),
    (
        "food_items",
        "ck_food_items_calories_range",
        f"calories IS NULL OR (calories >= {MIN_CALORIES} AND calories <= {MAX_CALORIES})",
    ),
    (
        "food_items",
        "ck_food_items_quantity_range",
        f"quantity IS NULL OR (quantity > 0 AND quantity <= {MAX_QUANTITY})",
    ),
    (
        "food_items",
        "ck_food_items_quantity_grams_range",
        f"quantity_grams IS NULL OR (quantity_grams > 0 AND quantity_grams <= {MAX_QUANTITY})",
    ),
    (
        "private_foods",
        "ck_private_foods_calories_range",
        f"calories_per_100g IS NULL OR (calories_per_100g >= {MIN_CALORIES} AND calories_per_100g <= {MAX_CALORIES})",
    ),
    (
        "nutrition_source_cache",
        "ck_nutrition_source_cache_calories_range",
        f"calories_per_100g IS NULL OR (calories_per_100g >= {MIN_CALORIES} AND calories_per_100g <= {MAX_CALORIES})",
    ),
    (
        "pending_nutrition_quotes",
        "ck_pending_nutrition_quotes_grams_range",
        f"grams > 0 AND grams <= {MAX_QUANTITY}",
    ),
    (
        "pending_nutrition_quotes",
        "ck_pending_nutrition_quotes_calories_range",
        f"calories_per_100g >= {MIN_CALORIES_PER_100G} AND calories_per_100g <= {MAX_CALORIES_PER_100G}",
    ),
    (
        "nutrition_evidence",
        "ck_nutrition_evidence_quantity_range",
        f"quantity_grams > 0 AND quantity_grams <= {MAX_QUANTITY}",
    ),
    (
        "nutrition_evidence",
        "ck_nutrition_evidence_calories_range",
        f"calories_per_100g >= {MIN_CALORIES_PER_100G} AND calories_per_100g <= {MAX_CALORIES_PER_100G}",
    ),
    (
        "nutrition_evidence",
        "ck_nutrition_evidence_total_calories_range",
        f"total_calories >= {MIN_CALORIES} AND total_calories <= {MAX_CALORIES}",
    ),
    (
        "user_settings",
        "ck_user_settings_calorie_target_range",
        f"calorie_target IS NULL OR (calorie_target >= {MIN_CALORIE_TARGET} AND calorie_target <= {MAX_CALORIE_TARGET})",
    ),
)


def upgrade() -> None:
    for table, name, condition in _CONSTRAINTS:
        op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    for table, name, _condition in reversed(_CONSTRAINTS):
        op.drop_constraint(name, table, type_="check")
