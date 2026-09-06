"""Integration tests for the search_food_history tool (issue #107).

Verifies aggregation across full history, count, first/last eaten, average
calories, recent entries, empty results, and ownership scoping."""

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.db.base import session_scope
from app.db.models.entries import FoodEntry
from app.domain.agent_types import AgentContext, ToolCall
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.services.journal_tool_executor import JournalToolExecutor


def _tool_call(name: str, **arguments) -> ToolCall:
    return ToolCall(id="t1", name=name, arguments=json.dumps(arguments))


def _entry(user_id: int, eaten_at: datetime, calories: int, description: str) -> FoodEntry:
    return FoodEntry(
        user_id=user_id,
        original_message=description,
        eaten_at=eaten_at,
        calories=calories,
        nutrition_source="manual",
        confidence="high",
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_search_food_history_aggregates_count_first_last_average_and_recent():
    executor = JournalToolExecutor()
    zone = ZoneInfo("Europe/Bucharest")
    today = datetime.now(UTC).astimezone(zone).date()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 600201, "History", "Europe/Bucharest")
        long_ago = datetime.combine(today - timedelta(days=30), datetime.min.time(), tzinfo=zone) + timedelta(hours=10)
        recent = datetime.combine(today - timedelta(days=2), datetime.min.time(), tzinfo=zone) + timedelta(hours=18)
        session.add(_entry(user.id, long_ago, 200, "yogurt with honey"))
        session.add(_entry(user.id, recent, 250, "greek yogurt"))
        session.add(_entry(user.id, datetime.combine(today - timedelta(days=10), datetime.min.time(), tzinfo=zone) + timedelta(hours=8), 180, "yogurt"))
        await session.commit()

        result = await executor.execute(
            session,
            AgentContext(user=user, chat_id="1", message="when did I last eat yogurt?"),
            _tool_call("search_food_history", query="yogurt"),
            [],
        )
    assert result.ok
    data = result.data
    assert data["query"] == "yogurt"
    assert data["count"] == 3
    assert data["averageCalories"] == 210  # (200 + 250 + 180) / 3
    assert data["lastEatenAt"] is not None
    assert data["firstEatenAt"] is not None
    # Most recent first
    assert data["recentEntries"][0]["description"] == "greek yogurt"
    assert len(data["recentEntries"]) == 3


@pytest.mark.asyncio
async def test_search_food_history_returns_empty_for_no_matches():
    executor = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 600202, "History", "Europe/Bucharest")
        await session.commit()
        result = await executor.execute(
            session,
            AgentContext(user=user, chat_id="1", message="pizza?"),
            _tool_call("search_food_history", query="pizza"),
            [],
        )
    assert result.ok
    assert result.data["count"] == 0
    assert result.data["recentEntries"] == []
    assert result.data["lastEatenAt"] is None


@pytest.mark.asyncio
async def test_search_food_history_requires_query():
    executor = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 600203, "History", "Europe/Bucharest")
        await session.commit()
        result = await executor.execute(
            session,
            AgentContext(user=user, chat_id="1", message="history"),
            _tool_call("search_food_history"),
            [],
        )
    assert not result.ok
    assert result.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_search_food_history_excludes_other_users():
    executor = JournalToolExecutor()
    zone = ZoneInfo("Europe/Bucharest")
    today = datetime.now(UTC).astimezone(zone).date()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 600204, "History", "Europe/Bucharest")
        other = await get_or_create_by_telegram_user_id(session, 600205, "Other", "Europe/Bucharest")
        session.add(_entry(user.id, datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=zone) + timedelta(hours=10), 200, "my yogurt"))
        session.add(_entry(other.id, datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=zone) + timedelta(hours=10), 9999, "their yogurt"))
        await session.commit()
        result = await executor.execute(
            session,
            AgentContext(user=user, chat_id="1", message="yogurt?"),
            _tool_call("search_food_history", query="yogurt"),
            [],
        )
    assert result.ok
    assert result.data["count"] == 1
    assert result.data["recentEntries"][0]["description"] == "my yogurt"
