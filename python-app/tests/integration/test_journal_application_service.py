from datetime import UTC, datetime

import pytest

from app.db.base import session_scope
from app.db.models.messaging import TelegramAccessGrant
from app.db.models.users import FoodUser
from app.domain.agent_types import AgentContext
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.services.journal_application_service import JournalApplicationService


async def _make_user(session, telegram_user_id: int = 555) -> FoodUser:
    return await get_or_create_by_telegram_user_id(session, telegram_user_id, "Tester", "Europe/Bucharest")


class _FakeAgent:
    """Records whether run()/run_undo() were invoked, without touching OpenAI
    or the tool executor -- these tests only assert routing, not undo's own
    tool-level behavior (covered separately in journal_tool_executor tests)."""

    def __init__(self, undo_reply: str = "Undid the latest journal change.") -> None:
        self.undo_reply = undo_reply
        self.run_calls: list[str] = []
        self.run_undo_calls: list[AgentContext] = []

    async def run(self, session, context: AgentContext) -> str:
        self.run_calls.append(context.message)
        return "agent reply"

    async def run_undo(self, session, context: AgentContext) -> str:
        self.run_undo_calls.append(context)
        return self.undo_reply


@pytest.mark.asyncio
async def test_start_shows_onboarding_prompt_for_a_new_user():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/start")
    assert "IANA" in reply or "timezone" in reply.lower()


@pytest.mark.asyncio
async def test_start_explains_what_the_bot_does_before_asking_for_a_timezone():
    """A new user's only guidance before this was a bare timezone request --
    confirmed live against a real onboarded user who was never told the bot
    logs meals from text/voice/photo and got stuck with no calorie target."""
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/start")
    lowered = reply.lower()
    assert "voice" in lowered or "vocală" in lowered
    assert "photo" in lowered or "poză" in lowered


@pytest.mark.asyncio
async def test_help_lists_all_commands():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/help")
    for cmd in ("/start", "/help", "/today", "/settings", "/cancel", "/privacy", "/undo", "/feedback"):
        assert cmd in reply
    assert "/adduser" not in reply


@pytest.mark.asyncio
async def test_private_admin_help_includes_access_commands_but_group_help_does_not():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session, 777)
        session.add(TelegramAccessGrant(telegram_user_id=777, is_admin=True, active=True, granted_by=None, created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))
        await session.commit()
        private_reply = await journal.handle(session, user, "777", "/help")
        group_reply = await journal.handle(session, user, "-1001", "/help")
    assert "/adduser" in private_reply
    assert "/removeuser" in private_reply
    assert "/adduser" not in group_reply


@pytest.mark.asyncio
async def test_today_reports_zero_for_a_fresh_user():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/today")
    assert "0 kcal" in reply


@pytest.mark.asyncio
async def test_settings_command_shows_the_day_boundary_and_reminder_state():
    from app.repositories.food_user_repo import get_settings

    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        settings = await get_settings(session, user.id)
        settings.day_boundary_hour = 4
        settings.day_boundary_reminder_enabled = True
        await session.commit()
        reply = await journal.handle(session, user, "1", "/settings")

    assert "4:00" in reply
    # Not a loose "on" in reply.lower() check: both languages' trailing
    # "conversațional"/"conversationally" already contain the substring "on",
    # which would make that assertion pass regardless of the actual state.
    assert "reminder on" in reply or "memento început zi pornit" in reply


@pytest.mark.asyncio
async def test_settings_command_shows_target_mode_and_notification_toggles():
    from app.repositories.food_user_repo import get_settings

    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        settings = await get_settings(session, user.id)
        settings.target_mode = "min"
        settings.budget_alerts_enabled = True
        settings.tracking_nudge_enabled = True
        await session.commit()
        reply = await journal.handle(session, user, "1", "/settings")

    assert "minimum" in reply.lower() or "minim" in reply.lower()
    assert "budget alerts on" in reply or "alerte buget pornite" in reply
    assert "tracking nudge on" in reply or "memento urmărire pornit" in reply


@pytest.mark.asyncio
async def test_feedback_command_stores_the_message_and_confirms():
    from sqlalchemy import select

    from app.db.models.feedback import UserFeedback

    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/feedback a weekly summary chart would help")
        await session.commit()

    assert "thank" in reply.lower() or "mulțumesc" in reply.lower()

    async with session_scope() as session:
        rows = (await session.execute(select(UserFeedback).where(UserFeedback.user_id == user.id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].message == "a weekly summary chart would help"
    assert rows[0].source == "command"


@pytest.mark.asyncio
async def test_feedback_command_without_text_prompts_for_it_and_stores_nothing():
    from sqlalchemy import select

    from app.db.models.feedback import UserFeedback

    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/feedback")
        await session.commit()

    assert "/feedback" in reply

    async with session_scope() as session:
        rows = (await session.execute(select(UserFeedback).where(UserFeedback.user_id == user.id))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_unknown_command_gets_a_helpful_message():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/nonexistent")
    assert "help" in reply.lower() or "ajuta" in reply.lower() or "necunosc" in reply.lower()


@pytest.mark.asyncio
async def test_romanian_message_gets_romanian_unavailable_reply_and_sets_preferred_language():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "cate calorii azi?")
        await session.commit()

    assert "Nu pot procesa" in reply
    async with session_scope() as session:
        from app.repositories.food_user_repo import get_settings

        settings = await get_settings(session, user.id)
        assert settings.preferred_language == "ro"


@pytest.mark.asyncio
async def test_english_message_gets_english_unavailable_reply():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "how many calories today")
    assert "cannot process" in reply


@pytest.mark.asyncio
async def test_slash_commands_do_not_change_preferred_language():
    """Commands use the user's LAST-SAVED preferred_language, not a fresh
    per-message detection -- sending a slash command must not overwrite it."""
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        await journal.handle(session, user, "1", "cate calorii azi?")  # sets preferred_language to "ro"
        await session.commit()

    async with session_scope() as session:
        from app.repositories.food_user_repo import get_settings

        settings = await get_settings(session, user.id)
        assert settings.preferred_language == "ro"
        reply = await journal.handle(session, user, "1", "/help")  # should stay Romanian
    assert "Comenzi" in reply


@pytest.mark.asyncio
async def test_undo_slash_command_invokes_the_agent_undo_tool_not_the_unknown_command_fallback():
    """Regression test: /undo used to fall through to command()'s deterministic
    dispatch table, which does not list /undo, so it silently returned "Unknown
    command. Use /help." with no test catching it. /undo must reach the same
    undo_last_change tool that natural-language undo already uses."""
    agent = _FakeAgent()
    journal = JournalApplicationService(default_timezone="Europe/Bucharest", agent=agent)
    async with session_scope() as session:
        user = await _make_user(session, 90001)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/undo")

    assert len(agent.run_undo_calls) == 1
    assert agent.run_undo_calls[0].message == "/undo"
    assert reply == agent.undo_reply
    assert "unknown" not in reply.lower() and "necunosc" not in reply.lower()
    assert not agent.run_calls  # must not spend a full model turn for a slash command


@pytest.mark.asyncio
async def test_undo_slash_command_without_an_agent_is_unavailable_not_unknown():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session, 90002)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/undo")
    # New users default to preferred_language="ro" (see UserSettings.preferred_language).
    assert "nu pot procesa" in reply.lower()
    assert "unknown" not in reply.lower() and "necunosc" not in reply.lower()
