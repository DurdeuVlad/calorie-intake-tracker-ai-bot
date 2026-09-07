"""Add kind, context, resolved columns to user_feedback and NAME onboarding stage.

Merges the v2.0 feedback extensions (kind, context, resolved) on top of the
remote feedback table (source, message, created_at). Also changes the default
onboarding_stage from TIMEZONE to NAME for the new name-first onboarding flow.
"""

import sqlalchemy as sa

from alembic import op

revision = "e9f5a2b7c8d3"
down_revision = "d38d2201ba5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_feedback", sa.Column("kind", sa.String(16), nullable=True, server_default="bug"))
    op.add_column("user_feedback", sa.Column("context", sa.Text(), nullable=True))
    op.add_column("user_feedback", sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.alter_column("user_settings", "onboarding_stage", existing_type=sa.String(), server_default="NAME")


def downgrade() -> None:
    op.alter_column("user_settings", "onboarding_stage", existing_type=sa.String(), server_default="TIMEZONE")
    op.drop_column("user_feedback", "resolved")
    op.drop_column("user_feedback", "context")
    op.drop_column("user_feedback", "kind")
