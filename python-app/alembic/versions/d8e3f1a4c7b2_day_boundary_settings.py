"""Add day_boundary_hour and day_boundary_reminder_enabled to user_settings."""

import sqlalchemy as sa

from alembic import op

revision = "d8e3f1a4c7b2"
down_revision = "c4a8e2f1b6d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("day_boundary_hour", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "user_settings",
        sa.Column("day_boundary_reminder_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_check_constraint(
        "ck_user_settings_day_boundary_hour_range",
        "user_settings",
        "day_boundary_hour >= 0 AND day_boundary_hour <= 23",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_settings_day_boundary_hour_range", "user_settings", type_="check")
    op.drop_column("user_settings", "day_boundary_reminder_enabled")
    op.drop_column("user_settings", "day_boundary_hour")
