"""Backfill onboarding_completed for users the pre-fix update_settings tool stranded mid-onboarding."""

import sqlalchemy as sa

from alembic import op

revision = "c4a8e2f1b6d9"
down_revision = "b3f7a1c9d4e2"
branch_labels = None
depends_on = None

# update_settings used to set timezone/calorieTarget without ever advancing
# onboarding_stage or onboarding_completed -- only the deterministic
# continue_onboarding() path did that, and it has no call site in production
# (see journal_application_service.py's module docstring). "Engaged but
# stuck" here means at least one message beyond the bare /start command.
_BACKFILL_SQL = """
    UPDATE user_settings
    SET onboarding_stage = 'COMPLETE', onboarding_completed = true
    WHERE onboarding_completed = false
      AND onboarding_stage IN ('TIMEZONE', 'CALORIE_TARGET')
      AND EXISTS (
          SELECT 1 FROM conversation_memory cm
          WHERE cm.user_id = user_settings.user_id
            AND cm.role = 'user'
            AND cm.content <> '/start'
      )
"""


def upgrade() -> None:
    op.execute(sa.text(_BACKFILL_SQL))


def downgrade() -> None:
    # Irreversible: nothing distinguishes a user this backfill completed from
    # one that would have completed onboarding normally by this point.
    pass
