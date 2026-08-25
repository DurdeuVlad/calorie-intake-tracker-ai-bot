"""baseline: schema as of Flyway V17 (no-op, stamp only)

This revision intentionally does nothing. The 18 live tables already exist in the
shared production Postgres database, created by the Java app's Flyway migrations
(V1-V17). On first deploy of this app against that database, run:

    alembic stamp 585aef501d2c

NOT `alembic upgrade head` -- stamping just records this revision as applied
without attempting to (re)create any table. All future schema changes should be
ordinary `alembic revision --autogenerate` migrations layered on top of this
baseline. `flyway_schema_history` is left in place, untouched, as a historical
record; Flyway itself is retired.

Revision ID: 585aef501d2c
Revises:
Create Date: 2026-08-18 20:50:52.892455

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '585aef501d2c'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
