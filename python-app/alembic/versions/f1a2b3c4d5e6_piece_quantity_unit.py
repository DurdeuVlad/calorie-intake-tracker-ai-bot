"""Allow the 'piece' quantity unit (e.g. 10 wings) on food_items."""

from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e9f5a2b7c8d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Constraint came from the Flyway baseline (V17); IF EXISTS keeps fresh create_all databases working.
    op.execute("ALTER TABLE food_items DROP CONSTRAINT IF EXISTS chk_food_items_quantity_unit")
    op.execute(
        "ALTER TABLE food_items ADD CONSTRAINT chk_food_items_quantity_unit "
        "CHECK (quantity_unit IN ('g','ml','piece','portion','unspecified'))"
    )


def downgrade() -> None:
    op.execute("UPDATE food_items SET quantity_unit = 'portion' WHERE quantity_unit = 'piece'")
    op.execute("ALTER TABLE food_items DROP CONSTRAINT IF EXISTS chk_food_items_quantity_unit")
    op.execute(
        "ALTER TABLE food_items ADD CONSTRAINT chk_food_items_quantity_unit "
        "CHECK (quantity_unit IN ('g','ml','portion','unspecified'))"
    )
