"""Verifies the c4a8e2f1b6d9 data migration's backfill logic in isolation from
Alembic's migration context (op.execute needs a live migration run, not a
plain session) by executing the identical SQL against the already-migrated
test database -- safe to re-run since the WHERE clause only matches rows still
onboarding_completed = false."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text

from app.db.base import session_scope
from app.db.models.conversation import ConversationMemory
from app.db.models.users import UserSettings
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id, get_settings

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


@pytest.mark.asyncio
async def test_backfill_completes_an_engaged_user_stuck_on_timezone():
    """Reproduces the real production case found live: /start, a timezone
    reply, then a follow-up the bot never explained anything after."""
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 9001, "Tester", "Europe/Bucharest")
        settings = await get_settings(session, user.id)
        settings.timezone = "Europe/Bucharest"
        now = datetime.now(UTC)
        session.add(ConversationMemory(user_id=user.id, role="user", content="/start", created_at=now))
        session.add(ConversationMemory(user_id=user.id, role="assistant", content="Welcome...", created_at=now))
        session.add(ConversationMemory(user_id=user.id, role="user", content="Bucharest", created_at=now))
        session.add(ConversationMemory(user_id=user.id, role="assistant", content="Timezone set.", created_at=now))
        session.add(ConversationMemory(user_id=user.id, role="user", content="okay", created_at=now))
        session.add(ConversationMemory(user_id=user.id, role="assistant", content="Bine.", created_at=now))
        await session.commit()

        await session.execute(text(_BACKFILL_SQL))
        await session.commit()

    async with session_scope() as session:
        settings = (await session.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one()
    assert settings.onboarding_completed is True
    assert settings.onboarding_stage == "COMPLETE"


@pytest.mark.asyncio
async def test_backfill_leaves_a_genuinely_new_user_alone():
    """A user who only ever sent /start and never replied must not be
    force-completed -- they haven't been told anything yet."""
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 9002, "Tester", "Europe/Bucharest")
        now = datetime.now(UTC)
        session.add(ConversationMemory(user_id=user.id, role="user", content="/start", created_at=now))
        session.add(ConversationMemory(user_id=user.id, role="assistant", content="Welcome...", created_at=now))
        await session.commit()

        await session.execute(text(_BACKFILL_SQL))
        await session.commit()

    async with session_scope() as session:
        settings = (await session.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one()
    assert settings.onboarding_completed is False
    assert settings.onboarding_stage == "TIMEZONE"


@pytest.mark.asyncio
async def test_backfill_does_not_touch_an_already_completed_user():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 9003, "Tester", "Europe/Bucharest")
        settings = await get_settings(session, user.id)
        settings.require_calorie_target()
        settings.calorie_target = 1900
        settings.skip_calorie_target()
        await session.commit()
        original_stage = settings.onboarding_stage

        await session.execute(text(_BACKFILL_SQL))
        await session.commit()

    async with session_scope() as session:
        settings = (await session.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one()
    assert settings.onboarding_completed is True
    assert settings.onboarding_stage == original_stage == "COMPLETE"
