"""Integration tests for the get_weekly_summary tool (issue #106).

Verifies per-day aggregation, weekly total, daily average, target reporting,
future-date rejection, and ownership scoping. Uses the real executor and a
real database session via session_scope."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.db.base import session_scope
from app.db.models.entries import FoodEntry
from app.domain.agent_types import AgentContext, ToolCall
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.services.journal_tool_executor import JournalToolExecutor


def _tool_call(name: str, **arguments) -> ToolCall:
    return ToolCall(id="t1", name=name, arguments=__import__("json").dumps(arguments))


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
async def test_weekly_summary_aggregates_per_day_and_returns_total_average_target():
    executor = JournalToolExecutor()
    zone = ZoneInfo("Europe/Bucharest")
    today = datetime.now(UTC).astimezone(zone).date()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 600106, "Weekly", "Europe/Bucharest")
        # Two entries today, one yesterday, one three days ago.
        session.add(_entry(user.id, datetime.combine(today, datetime.min.time(), tzinfo=zone) + timedelta(hours=10), 200, "yogurt"))
        session.add(_entry(user.id, datetime.combine(today, datetime.min.time(), tzinfo=zone) + timedelta(hours=14), 300, "soup"))
        yesterday = today - timedelta(days=1)
        session.add(_entry(user.id, datetime.combine(yesterday, datetime.min.time(), tzinfo=zone) + timedelta(hours=9), 150, "toast"))
        three_days_ago = today - timedelta(days=3)
        session.add(_entry(user.id, datetime.combine(three_days_ago, datetime.min.time(), tzinfo=zone) + timedelta(hours=12), 400, "pasta"))
        await session.commit()

        result = await executor.execute(
            session,
            AgentContext(user=user, chat_id="1", message="weekly summary"),
            _tool_call("get_weekly_summary"),
            [],
        )
    assert result.ok
    data = result.data
    assert data["endDate"] == today.isoformat()
    assert data["startDate"] == (today - timedelta(days=6)).isoformat()
    assert data["weeklyCalories"] == 1050
    assert data["dailyAverage"] == 150
    assert data["target"] == "unset"  # default user has no target
    days_by_date = {d["date"]: d for d in data["days"]}
    assert days_by_date[today.isoformat()]["calories"] == 500
    assert days_by_date[today.isoformat()]["entries"] == 2
    assert days_by_date[yesterday.isoformat()]["calories"] == 150
    assert days_by_date[three_days_ago.isoformat()]["calories"] == 400
    # Days with no entries report zero.
    empty_day = (today - timedelta(days=2)).isoformat()
    assert days_by_date[empty_day]["calories"] == 0
    assert days_by_date[empty_day]["entries"] == 0
    assert len(data["days"]) == 7


@pytest.mark.asyncio
async def test_today_summary_uses_inbound_receipt_time_for_delayed_messages():
    executor = JournalToolExecutor()
    zone = ZoneInfo("Europe/Bucharest")
    received_at = datetime(2024, 1, 31, 23, 59, tzinfo=UTC)
    received_local_date = received_at.astimezone(zone).date()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 600110, "Delayed", "Europe/Bucharest")
        session.add(
            _entry(
                user.id,
                datetime.combine(received_local_date, datetime.min.time(), tzinfo=zone) + timedelta(minutes=30),
                275,
                "delayed meal",
            )
        )
        await session.commit()

        result = await executor.execute(
            session,
            AgentContext(
                user=user,
                chat_id="1",
                message="how many calories today",
                started_at=received_at,
            ),
            _tool_call("get_today_summary"),
            [],
        )

    assert result.ok
    assert result.data["calories"] == 275
    assert result.data["entries"] == 1


@pytest.mark.asyncio
async def test_weekly_summary_rejects_future_reference_date():
    executor = JournalToolExecutor()
    zone = ZoneInfo("Europe/Bucharest")
    today = datetime.now(UTC).astimezone(zone).date()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 600107, "Weekly", "Europe/Bucharest")
        await session.commit()
        result = await executor.execute(
            session,
            AgentContext(user=user, chat_id="1", message="next week"),
            _tool_call("get_weekly_summary", date=(today + timedelta(days=1)).isoformat()),
            [],
        )
    assert not result.ok
    assert result.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_weekly_summary_excludes_other_users_entries():
    executor = JournalToolExecutor()
    zone = ZoneInfo("Europe/Bucharest")
    today = datetime.now(UTC).astimezone(zone).date()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 600108, "Weekly", "Europe/Bucharest")
        other = await get_or_create_by_telegram_user_id(session, 600109, "Other", "Europe/Bucharest")
        session.add(_entry(user.id, datetime.combine(today, datetime.min.time(), tzinfo=zone) + timedelta(hours=10), 200, "mine"))
        session.add(_entry(other.id, datetime.combine(today, datetime.min.time(), tzinfo=zone) + timedelta(hours=10), 9999, "not mine"))
        await session.commit()
        result = await executor.execute(
            session,
            AgentContext(user=user, chat_id="1", message="weekly"),
            _tool_call("get_weekly_summary"),
            [],
        )
    assert result.ok
    assert result.data["weeklyCalories"] == 200
