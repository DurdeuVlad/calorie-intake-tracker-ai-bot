"""Tests for the feedback tool and /bug command."""

from datetime import UTC, datetime

import pytest

from app.db.base import session_scope
from app.db.models.users import FoodUser
from app.domain.agent_types import AgentContext
from app.repositories import feedback_repo
from app.tools.feedback import save_feedback


async def _create_user() -> FoodUser:
    async with session_scope() as session:
        user = FoodUser(telegram_user_id=999, display_name="Feedback Tester", created_at=datetime.now(UTC))
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.mark.asyncio
async def test_save_feedback_success():
    """save_feedback persists a bug report scoped to the user."""
    user = await _create_user()
    async with session_scope() as session:
        context = AgentContext(user=user, chat_id="1", message="test")
        result = await save_feedback(None, session, context, {"kind": "bug", "message": "a logat pizza de doua ori"}, [])
        assert result.ok
        assert result.data["saved"] is True
        assert result.data["kind"] == "bug"
        await session.commit()


@pytest.mark.asyncio
async def test_save_feedback_correction_kind():
    """save_feedback accepts 'correction' as a kind."""
    user = await _create_user()
    async with session_scope() as session:
        context = AgentContext(user=user, chat_id="1", message="test")
        result = await save_feedback(None, session, context, {"kind": "correction", "message": "calorii gresite"}, [])
        assert result.ok
        assert result.data["kind"] == "correction"
        await session.commit()


@pytest.mark.asyncio
async def test_save_feedback_invalid_kind_defaults_to_bug():
    """Invalid kind defaults to 'bug'."""
    user = await _create_user()
    async with session_scope() as session:
        context = AgentContext(user=user, chat_id="1", message="test")
        result = await save_feedback(None, session, context, {"kind": "hacked", "message": "test"}, [])
        assert result.ok
        assert result.data["kind"] == "bug"
        await session.commit()


@pytest.mark.asyncio
async def test_save_feedback_empty_message_rejected():
    """Empty message is rejected."""
    user = await _create_user()
    async with session_scope() as session:
        context = AgentContext(user=user, chat_id="1", message="test")
        result = await save_feedback(None, session, context, {"kind": "bug", "message": ""}, [])
        assert not result.ok


@pytest.mark.asyncio
async def test_save_feedback_no_message_rejected():
    """Missing message is rejected."""
    user = await _create_user()
    async with session_scope() as session:
        context = AgentContext(user=user, chat_id="1", message="test")
        result = await save_feedback(None, session, context, {"kind": "bug"}, [])
        assert not result.ok


@pytest.mark.asyncio
async def test_save_feedback_with_context():
    """Context is saved when provided."""
    user = await _create_user()
    async with session_scope() as session:
        context = AgentContext(user=user, chat_id="1", message="test")
        result = await save_feedback(
            None, session, context,
            {"kind": "bug", "message": "wrong", "context": "user said X, bot did Y"},
            [],
        )
        assert result.ok
        await session.commit()


@pytest.mark.asyncio
async def test_recent_feedback_returns_user_scoped():
    """recent_for_user returns only the user's feedback, oldest first."""
    user = await _create_user()
    async with session_scope() as session:
        await feedback_repo.save(session, user, kind="bug", message="test1")
        await feedback_repo.save(session, user, kind="correction", message="test2")
        await session.commit()
    async with session_scope() as session:
        recent = await feedback_repo.recent_for_user(session, user)
        assert len(recent) == 2
        assert recent[0].message == "test1"
        assert recent[1].message == "test2"