"""Change onboarding default stage from TIMEZONE to NAME."""

import sqlalchemy as sa

from alembic import op

revision = "a8b4c0d6e305"
down_revision = "f7a3b9c5d204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing users who already completed onboarding stay COMPLETE.
    # Existing users mid-onboarding (TIMEZONE) stay TIMEZONE — they already
    # provided their name implicitly or don't need the new NAME stage.
    # Only NEW users get NAME as the default (enforced by the server_default).
    op.alter_column(
        "user_settings",
        "onboarding_stage",
        existing_type=sa.String(),
        server_default="NAME",
    )


def downgrade() -> None:
    op.alter_column(
        "user_settings",
        "onboarding_stage",
        existing_type=sa.String(),
        server_default="TIMEZONE",
    )
