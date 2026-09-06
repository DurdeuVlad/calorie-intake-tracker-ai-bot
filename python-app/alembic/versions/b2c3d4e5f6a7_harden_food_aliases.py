"""Harden food aliases: case-insensitive unique constraint and check constraints (issue #108 adversarial review).

Adds a stored generated column `alias_lower` with a unique constraint on
(user_id, alias_lower) so case-variant duplicates cannot coexist. Adds CHECK
constraints enforcing calorie ranges and mutual exclusion. The original
case-sensitive unique constraint is dropped because the case-insensitive
constraint supersedes it."""

import sqlalchemy as sa

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the case-sensitive unique constraint; the case-insensitive
    # constraint below enforces the actual invariant.
    op.drop_constraint("uq_food_aliases_user_alias", "food_aliases", type_="unique")

    # Add a stored generated column for case-insensitive matching.
    op.execute(
        "ALTER TABLE food_aliases "
        "ADD COLUMN alias_lower VARCHAR(255) GENERATED ALWAYS AS (lower(alias)) STORED"
    )

    op.create_unique_constraint(
        "uq_food_aliases_user_alias_ci",
        "food_aliases",
        ["user_id", "alias_lower"],
    )
    op.create_check_constraint(
        "ck_alias_cph_range",
        "food_aliases",
        "calories_per_100g IS NULL OR (calories_per_100g > 0 AND calories_per_100g <= 10000)",
    )
    op.create_check_constraint(
        "ck_alias_fixed_range",
        "food_aliases",
        "fixed_calories IS NULL OR (fixed_calories >= 0 AND fixed_calories <= 10000)",
    )
    op.create_check_constraint(
        "ck_alias_one_calorie",
        "food_aliases",
        "NOT (calories_per_100g IS NOT NULL AND fixed_calories IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_check_constraint("food_aliases", "ck_alias_one_calorie")
    op.drop_check_constraint("food_aliases", "ck_alias_fixed_range")
    op.drop_check_constraint("food_aliases", "ck_alias_cph_range")
    op.drop_constraint("uq_food_aliases_user_alias_ci", "food_aliases", type_="unique")
    op.drop_column("food_aliases", "alias_lower")
    op.create_unique_constraint(
        "uq_food_aliases_user_alias", "food_aliases", ["user_id", "alias"]
    )
