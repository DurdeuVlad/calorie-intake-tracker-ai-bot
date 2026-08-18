from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.db.base import session_scope
from app.db.models.conversation import ConversationMemory
from app.db.models.users import FoodUser
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.services.journal_application_service import JournalApplicationService


async def _make_user(session, telegram_user_id: int = 555) -> FoodUser:
    return await get_or_create_by_telegram_user_id(session, telegram_user_id, "Tester", "Europe/Bucharest")


@pytest.mark.asyncio
async def test_start_shows_onboarding_prompt_for_a_new_user():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/start")
    assert "IANA" in reply or "timezone" in reply.lower()


@pytest.mark.asyncio
async def test_help_lists_all_commands():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/help")
    for cmd in ("/start", "/help", "/today", "/settings", "/cancel", "/privacy"):
        assert cmd in reply


@pytest.mark.asyncio
async def test_today_reports_zero_for_a_fresh_user():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    async with session_scope() as session:
        user = await _make_user(session)
        await session.commit()
        reply = await journal.handle(session, user, "1", "/today")
    assert "0 kcal" in reply


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
