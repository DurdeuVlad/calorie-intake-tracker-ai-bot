"""Add target_mode, budget_alerts_enabled, tracking_nudge_enabled to user_settings."""

import sqlalchemy as sa

from alembic import op

revision = "a1b5e9c3f8d4"
down_revision = "d8e3f1a4c7b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("target_mode", sa.String(length=8), server_default="max", nullable=False),
    )
    op.add_column(
        "user_settings",
        sa.Column("budget_alerts_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "user_settings",
        sa.Column("tracking_nudge_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_check_constraint(
        "ck_user_settings_target_mode_valid",
        "user_settings",
        "target_mode IN ('max', 'min')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_settings_target_mode_valid", "user_settings", type_="check")
    op.drop_column("user_settings", "tracking_nudge_enabled")
    op.drop_column("user_settings", "budget_alerts_enabled")
    op.drop_column("user_settings", "target_mode")
