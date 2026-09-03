"""Shared with alembic/versions/c4a8e2f1b6d9_backfill_stuck_onboarding.py and its
test -- a single source of truth so the two can't silently drift apart."""

STUCK_ONBOARDING_BACKFILL_SQL = """
    UPDATE user_settings
    SET onboarding_stage = 'COMPLETE', onboarding_completed = true
    WHERE onboarding_completed = false
      AND onboarding_stage IN ('TIMEZONE', 'CALORIE_TARGET')
      AND EXISTS (
          SELECT 1 FROM conversation_memory cm
          WHERE cm.user_id = user_settings.user_id
            AND cm.role = 'user'
            AND lower(trim(cm.content)) <> '/start'
      )
"""
