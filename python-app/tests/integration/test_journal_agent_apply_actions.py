"""End-to-end test of the agent loop + tool executor, using a stub model that
plays back a pre-programmed script instead of calling the real OpenAI API.
This exercises the exact same code path a real conversation would, just with
the LLM itself replaced.

v2.0: The model writes full replies from structured tool results. Tests assert
key facts in the reply (calories, undo mention) without requiring exact
template strings. The ScriptedModel provides a text reply after tool calls."""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.agent.journal_agent import JournalAgent
from app.agent.openai_model_client import AgentProviderUnavailableError
from app.db.base import session_scope
from app.db.models.entries import FoodEntry, FoodItem
from app.db.models.feedback import UserFeedback
from app.db.models.journal_changes import JournalChangeSet
from app.db.models.messaging import (
    MessagingOutboundMessage,
    MessagingRoute,
    PinnedDailyStatus,
)
from app.db.models.nutrition import NutritionEvidence, PendingNutritionQuote
from app.db.models.users import FoodUser, UserSettings
from app.domain.agent_types import AgentContext, AgentReply, ToolCall
from app.messaging import execution_context
from app.repositories import food_entry_repo, food_user_repo
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.services import daily_status_service
from app.services.journal_tool_executor import JournalToolExecutor


class ScriptedModel:
    """Returns one AgentReply per call to next(), in order."""

    def __init__(self, replies: list[AgentReply]) -> None:
        self._replies = list(replies)
        self.calls = 0

    async def next(self, context, memory, exchanges, feedback=None):
        reply = self._replies[self.calls]
        self.calls += 1
        return reply


class FailingModel:
    async def next(self, context, memory, exchanges, feedback=None):
        raise AgentProviderUnavailableError("simulated network failure")


class FailingAfterToolModel:
    def __init__(self, tool_call: ToolCall) -> None:
        self.tool_call = tool_call
        self.calls = 0

    async def next(self, context, memory, exchanges, feedback=None):
        self.calls += 1
        if self.calls == 1:
            return AgentReply(None, [self.tool_call])
        raise AgentProviderUnavailableError("simulated receipt-generation failure")


def _tool_call(tool_id: str, name: str, **arguments) -> ToolCall:
    return ToolCall(id=tool_id, name=name, arguments=json.dumps(arguments))


def _text_reply(text: str) -> AgentReply:
    return AgentReply(text, [])


async def _reload_user(session, user_id: int) -> FoodUser:
    return (await session.execute(select(FoodUser).where(FoodUser.id == user_id))).scalar_one()


@pytest.mark.asyncio
async def test_create_action_accepts_hour_only_local_time_from_a_natural_language_request():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "cafea", "calories": 20, "localTime": "9"}])],
            ),
            _text_reply("Notat: cafea — 20 kcal. Trimite Undo în 10 minute pentru a anula."),
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 110, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(
            session,
            AgentContext(user=user, chat_id="1", message="noteaza pe ora 9", started_at=started_at),
        )
        await session.commit()

    assert "cafea" in reply
    assert "20" in reply
    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalar_one()
    assert entry.eaten_at == datetime(2026, 4, 1, 6, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_save_feedback_tool_stores_the_message_and_lets_the_model_confirm_in_its_own_words():
    """save_feedback has no canonical-reply branch (like save_private_food and
    update_settings), so the loop continues to a second model turn for the
    confirmation text -- this exercises that full round trip, not just the tool."""
    model = ScriptedModel(
        [
            AgentReply(None, [_tool_call("f1", "save_feedback", message="please add a weekly summary chart")]),
            AgentReply("Thanks, I've noted that.", []),
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 111, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(
            session,
            AgentContext(user=user, chat_id="1", message="you should add a weekly chart", started_at=started_at),
        )
        await session.commit()

    assert reply == "Thanks, I've noted that."
    async with session_scope() as session:
        rows = (await session.execute(select(UserFeedback).where(UserFeedback.user_id == user.id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].message == "please add a weekly summary chart"
    assert rows[0].source == "ai_detected"


@pytest.mark.asyncio
async def test_save_feedback_tool_rejects_empty_text():
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 112, "Tester", "Europe/Bucharest")
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="", started_at=started_at)
        result = await executor.execute(session, context, _tool_call("f2", "save_feedback", message="   "), [])

    assert result.ok is False


@pytest.mark.asyncio
async def test_get_recent_feedback_returns_the_callers_own_submissions_newest_first():
    """Live production regression: asked "what feedback did you log?", the
    agent had no way to answer and called save_feedback again with the same
    text, creating a duplicate row. This tool exists so it can answer honestly
    instead."""
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 117, "Tester", "Europe/Bucharest")
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="feedback", started_at=started_at)
        await executor.execute(session, context, _tool_call("f3", "save_feedback", message="first complaint"), [])
        await executor.execute(session, context, _tool_call("f4", "save_feedback", message="second complaint"), [])
        await session.commit()

        result = await executor.execute(session, context, _tool_call("f5", "get_recent_feedback"), [])
        await session.commit()

    assert result.ok is True
    messages = [row["message"] for row in result.data["feedback"]]
    assert messages == ["second complaint", "first complaint"]


@pytest.mark.asyncio
async def test_get_recent_feedback_is_scoped_to_the_caller_not_other_users():
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        owner = await get_or_create_by_telegram_user_id(session, 118, "Tester", "Europe/Bucharest")
        other = await get_or_create_by_telegram_user_id(session, 119, "Other", "Europe/Bucharest")
        await session.commit()
        owner_context = AgentContext(user=owner, chat_id="1", message="feedback", started_at=started_at)
        other_context = AgentContext(user=other, chat_id="2", message="feedback", started_at=started_at)
        await executor.execute(session, owner_context, _tool_call("f6", "save_feedback", message="owner's feedback"), [])
        await executor.execute(session, other_context, _tool_call("f7", "save_feedback", message="other user's feedback"), [])
        await session.commit()

        result = await executor.execute(session, owner_context, _tool_call("f8", "get_recent_feedback"), [])

    assert result.ok is True
    messages = [row["message"] for row in result.data["feedback"]]
    assert messages == ["owner's feedback"]


@pytest.mark.asyncio
async def test_update_settings_advances_onboarding_from_timezone_to_calorie_target():
    """Onboarding is driven by the agent calling update_settings during
    conversation -- it is the only path that reaches real onboarding users,
    so it must drive the same stage transitions."""
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 113, "Tester", "Europe/Bucharest")
        settings = await food_user_repo.get_settings(session, user.id)
        settings.require_timezone()
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="Bucharest", started_at=started_at)
        result = await executor.execute(session, context, _tool_call("s1", "update_settings", timezone="Europe/Bucharest"), [])
        await session.commit()

    assert result.ok is True
    async with session_scope() as session:
        settings = await food_user_repo.get_settings(session, user.id)
    assert settings.timezone == "Europe/Bucharest"
    assert settings.onboarding_stage == "CALORIE_TARGET"
    assert settings.onboarding_completed is False


@pytest.mark.asyncio
async def test_update_settings_completes_onboarding_with_a_calorie_target():
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 114, "Tester", "Europe/Bucharest")
        settings = await food_user_repo.get_settings(session, user.id)
        settings.require_calorie_target()
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="1900", started_at=started_at)
        result = await executor.execute(session, context, _tool_call("s2", "update_settings", calorieTarget=1900), [])
        await session.commit()

    assert result.ok is True
    async with session_scope() as session:
        settings = await food_user_repo.get_settings(session, user.id)
    assert settings.calorie_target == 1900
    assert settings.onboarding_stage == "COMPLETE"
    assert settings.onboarding_completed is True


@pytest.mark.asyncio
async def test_update_settings_completes_onboarding_with_an_explicit_skip():
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 115, "Tester", "Europe/Bucharest")
        settings = await food_user_repo.get_settings(session, user.id)
        settings.require_calorie_target()
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="skip", started_at=started_at)
        result = await executor.execute(session, context, _tool_call("s3", "update_settings", skipCalorieTarget=True), [])
        await session.commit()

    assert result.ok is True
    async with session_scope() as session:
        settings = await food_user_repo.get_settings(session, user.id)
    assert settings.calorie_target is None
    assert settings.onboarding_stage == "COMPLETE"
    assert settings.onboarding_completed is True


@pytest.mark.asyncio
async def test_update_settings_does_not_touch_onboarding_state_once_already_complete():
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 116, "Tester", "Europe/Bucharest")
        settings = await food_user_repo.get_settings(session, user.id)
        settings.require_calorie_target()
        settings.calorie_target = 1800
        settings.skip_calorie_target()
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="move to London time", started_at=started_at)
        result = await executor.execute(session, context, _tool_call("s4", "update_settings", timezone="Europe/London"), [])
        await session.commit()

    assert result.ok is True
    async with session_scope() as session:
        settings = await food_user_repo.get_settings(session, user.id)
    assert settings.timezone == "Europe/London"
    assert settings.onboarding_stage == "COMPLETE"
    assert settings.onboarding_completed is True


@pytest.mark.asyncio
async def test_update_settings_sets_day_boundary_hour_and_reminder_flag():
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 120, "Tester", "Europe/Bucharest")
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="make my day start at 4am", started_at=started_at)
        result = await executor.execute(
            session, context, _tool_call("s5", "update_settings", dayBoundaryHour=4, dayBoundaryReminderEnabled=True), []
        )
        await session.commit()

    assert result.ok is True
    async with session_scope() as session:
        settings = await food_user_repo.get_settings(session, user.id)
    assert settings.day_boundary_hour == 4
    assert settings.day_boundary_reminder_enabled is True


@pytest.mark.asyncio
async def test_update_settings_rejects_an_out_of_range_day_boundary_hour():
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 121, "Tester", "Europe/Bucharest")
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="make my day start at 25", started_at=started_at)
        result = await executor.execute(session, context, _tool_call("s6", "update_settings", dayBoundaryHour=24), [])

    assert result.ok is False


@pytest.mark.asyncio
async def test_update_settings_sets_target_mode_and_notification_toggles():
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 123, "Tester", "Europe/Bucharest")
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="I need to eat more, alert me", started_at=started_at)
        result = await executor.execute(
            session, context,
            _tool_call("s7", "update_settings", targetMode="min", budgetAlertsEnabled=True, trackingNudgeEnabled=True),
            [],
        )
        await session.commit()

    assert result.ok is True
    async with session_scope() as session:
        settings = await food_user_repo.get_settings(session, user.id)
    assert settings.target_mode == "min"
    assert settings.budget_alerts_enabled is True
    assert settings.tracking_nudge_enabled is True


@pytest.mark.asyncio
async def test_update_settings_rejects_an_invalid_target_mode():
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 124, "Tester", "Europe/Bucharest")
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="set target mode to average", started_at=started_at)
        result = await executor.execute(session, context, _tool_call("s8", "update_settings", targetMode="average"), [])

    assert result.ok is False


@pytest.mark.asyncio
async def test_get_today_summary_reports_the_target_mode():
    executor = JournalToolExecutor()
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 125, "Tester", "Europe/Bucharest")
        settings = await food_user_repo.get_settings(session, user.id)
        settings.target_mode = "min"
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="cate calorii azi", started_at=started_at)
        result = await executor.execute(session, context, _tool_call("s9", "get_today_summary"), [])

    assert result.ok is True
    assert result.data["targetMode"] == "min"


@pytest.mark.asyncio
async def test_budget_alert_fires_once_when_crossing_the_target_in_max_mode():
    """End-to-end through the food-logging path: apply_journal_actions calls
    the injected send_budget_alert callback the same way it already calls
    refresh_daily_status, right after a successful mutation."""
    from app.db.models.reports import ReportDelivery
    from app.scheduling import report_scheduler

    executor = JournalToolExecutor(send_budget_alert=report_scheduler.maybe_send_budget_alert_for_tool_executor)
    # maybe_send_budget_alert_for_tool_executor uses real datetime.now(zone) to
    # resolve "today" -- mirroring daily_status_service.refresh_for_tool_executor's
    # existing pattern, not something this PR introduces -- so started_at must be
    # real "now" too, or the CREATE's eaten_at and the alert's today_totals query
    # land on different calendar days and the alert never sees the new entry.
    started_at = datetime.now(UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 126, "Tester", "Europe/Bucharest")
        settings = await food_user_repo.get_settings(session, user.id)
        settings.calorie_target = 2000
        settings.budget_alerts_enabled = True
        session.add(MessagingRoute(user_id=user.id, provider="telegram", conversation_id="1"))
        await session.commit()

        context = AgentContext(user=user, chat_id="1", message="mancare mare", started_at=started_at)
        result = await executor.execute(
            session, context,
            _tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "mancare mare", "calories": 2100}]),
            [],
        )
        assert result.ok is True
        await session.commit()

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
        outbound = (await session.execute(select(MessagingOutboundMessage).where(MessagingOutboundMessage.conversation_id == "1")))
        outbound_rows = outbound.scalars().all()

    assert [d for d in deliveries if d.report_type == "budget_100"] != []
    assert any("2100/2000" in m.text for m in outbound_rows)


@pytest.mark.asyncio
async def test_budget_alert_does_not_fire_without_opt_in():
    executor = JournalToolExecutor()  # default send_budget_alert is a no-op
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 127, "Tester", "Europe/Bucharest")
        settings = await food_user_repo.get_settings(session, user.id)
        settings.calorie_target = 2000
        # budget_alerts_enabled defaults to False -- leave it as-is.
        await session.commit()

        context = AgentContext(user=user, chat_id="1", message="mancare mare", started_at=started_at)
        result = await executor.execute(
            session, context,
            _tool_call("c2", "apply_journal_actions", actions=[{"type": "CREATE", "description": "mancare mare", "calories": 2100}]),
            [],
        )
        assert result.ok is True
        await session.commit()

    from app.db.models.reports import ReportDelivery

    async with session_scope() as session:
        deliveries = (await session.execute(select(ReportDelivery).where(ReportDelivery.user_id == user.id))).scalars().all()
    assert deliveries == []


@pytest.mark.asyncio
async def test_search_entries_respects_a_custom_day_boundary_for_today():
    """A meal logged at 2am with a 4am boundary must still show up under
    "today" for the tracking day that hasn't rolled over yet -- and must NOT
    show up under the new calendar date's "today" once the boundary is crossed
    the other way."""
    executor = JournalToolExecutor()

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 122, "Tester", "Europe/Bucharest")
        settings = await food_user_repo.get_settings(session, user.id)
        settings.day_boundary_hour = 4
        await session.commit()

        # 2026-09-02 02:00 Europe/Bucharest -- before the 4am boundary, so it
        # belongs to the 2026-09-01 tracking day, not 2026-09-02.
        two_am = datetime(2026, 9, 2, 2, 0, tzinfo=ZoneInfo("Europe/Bucharest"))
        create_context = AgentContext(user=user, chat_id="1", message="cafea", started_at=two_am.astimezone(UTC))
        create_result = await executor.execute(
            session, create_context,
            _tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "cafea", "calories": 50}]),
            [],
        )
        assert create_result.ok is True
        await session.commit()

        # Still "before the boundary" at 03:30 the same morning -- the coffee
        # should show up under "today" (the 2026-09-01 tracking day). Passing
        # date="today" explicitly (rather than the no-args path _for_today()
        # uses) is what makes this resolve from context.started_at instead of
        # real wall-clock time, so the simulated hour actually takes effect.
        still_before_boundary = datetime(2026, 9, 2, 3, 30, tzinfo=ZoneInfo("Europe/Bucharest")).astimezone(UTC)
        today_context = AgentContext(user=user, chat_id="1", message="ce am mancat azi", started_at=still_before_boundary)
        today_result = await executor.execute(session, today_context, _tool_call("s1", "search_entries", date="today"), [])
        assert today_result.ok is True
        assert len(today_result.data["entries"]) == 1

        # After the boundary rolls over (05:00 the same calendar day), the
        # coffee belongs to the *previous* tracking day and must not appear.
        after_boundary = datetime(2026, 9, 2, 5, 0, tzinfo=ZoneInfo("Europe/Bucharest")).astimezone(UTC)
        after_context = AgentContext(user=user, chat_id="1", message="ce am mancat azi", started_at=after_boundary)
        after_result = await executor.execute(session, after_context, _tool_call("s2", "search_entries", date="today"), [])

    assert after_result.ok is True
    assert after_result.data["entries"] == []


@pytest.mark.asyncio
async def test_search_entries_finds_a_dated_entry_when_the_query_diacritics_differ():
    """Live production regression: two entries were logged as "dulceață de
    ardei iute" (with diacritics), the user asked to delete one, and
    search_entries with date="today" + a query missing diacritics
    ("dulceata de ardei iute") returned zero rows -- the agent then told the
    user, falsely, that it could not find any matching entry. Plain .lower()
    treats 'ă'/'ț' as distinct from 'a'/'t', so an exact substring match on
    diacritics never fires unless the user retypes the food name exactly as
    it was first logged."""
    executor = JournalToolExecutor()
    started_at = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 123, "Tester", "Europe/Bucharest")
        context = AgentContext(user=user, chat_id="1", message="sterge una", started_at=started_at)
        for _ in range(2):
            create_result = await executor.execute(
                session, context,
                _tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "dulceață de ardei iute", "calories": 156}]),
                [],
            )
            assert create_result.ok is True
        await session.commit()

        result = await executor.execute(
            session, context,
            _tool_call("s1", "search_entries", date="today", query="dulceata de ardei iute"),
            [],
        )

    assert result.ok is True
    assert len(result.data["entries"]) == 2


@pytest.mark.asyncio
async def test_create_action_logs_a_meal_and_reports_it_canonically():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "mic dejun", "calories": 600}])],
            ),
            _text_reply("Notat: mic dejun — 600 kcal. Trimite Undo în 10 minute."),
        ]
    )
    tools = JournalToolExecutor()
    agent = JournalAgent(model, tools, max_tool_calls=10)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 111, "Tester", "Europe/Bucharest")
        await session.commit()
        context = AgentContext(user=user, chat_id="1", message="mic dejun 600 kcal")
        reply = await agent.run(session, context)
        await session.commit()

    assert "mic dejun" in reply
    assert "600" in reply

    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert len(entries) == 1
    assert entries[0].calories == 600


@pytest.mark.asyncio
async def test_create_then_edit_then_undo_restores_the_original_entry():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 222, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    model1 = ScriptedModel([
        AgentReply(None, [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "salata", "calories": 300}])]),
        _text_reply("Notat: salata — 300 kcal."),
    ])
    agent1 = JournalAgent(model1, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await agent1.run(session, AgentContext(user=user, chat_id="1", message="salata 300 kcal"))
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry_id = entry.id
        assert entry.calories == 300

    model2 = ScriptedModel([
        AgentReply(None, [_tool_call("c2", "apply_journal_actions", actions=[{"type": "EDIT", "entryId": entry_id, "calories": 450}])]),
        _text_reply("Modificat: salata — 450 kcal. Undo disponibil 10 minute."),
    ])
    agent2 = JournalAgent(model2, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply2 = await agent2.run(session, AgentContext(user=user, chat_id="1", message="am fost 450 kcal de fapt"))
        await session.commit()
    assert "450" in reply2

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.calories == 450

    model3 = ScriptedModel([
        AgentReply(None, [_tool_call("c3", "undo_last_change")]),
        _text_reply("Anulat: salata (450 kcal)."),
    ])
    agent3 = JournalAgent(model3, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply3 = await agent3.run(session, AgentContext(user=user, chat_id="1", message="undo"))
        await session.commit()
    assert "salata" in reply3.lower() or "anulat" in reply3.lower()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.calories == 300


@pytest.mark.asyncio
async def test_move_requires_date_and_undo_preserves_nutrition_evidence():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 223, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    create_model = ScriptedModel([
        AgentReply(None, [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "description": "evidence meal", "calories": 200}])]),
        _text_reply("Logged evidence meal."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(create_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="evidence meal")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        item = (await session.execute(select(FoodItem).where(FoodItem.entry_id == entry.id))).scalar_one()
        original_when = entry.eaten_at
        session.add(
            NutritionEvidence(
                evidence_id=uuid.uuid4(),
                food_entry_id=entry.id,
                food_item_id=item.id,
                selected_quote_id=None,
                provider="open_food_facts",
                source_name="Open Food Facts",
                source_url="https://world.openfoodfacts.org/product/12345678",
                source_query="evidence meal",
                selected_candidate='{"name":"evidence meal"}',
                quantity_grams=Decimal("100.00"),
                calories_per_100g=200,
                total_calories=200,
                derivation="100 g × 200 kcal/100 g = 200 kcal",
                confidence="high",
                source_fetched_at=None,
                source_cache_hit=False,
                captured_at=datetime.now(UTC),
            )
        )
        await session.commit()
        entry_id = entry.id

    missing_date_model = ScriptedModel([
        AgentReply(None, [_tool_call("move-missing-date", "apply_journal_actions", actions=[{"type": "MOVE", "entryId": entry_id}])]),
        _text_reply("A date is required to move that entry."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply = await JournalAgent(missing_date_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="move it")
        )
        await session.commit()
    assert "required" in reply.lower()

    move_model = ScriptedModel([
        AgentReply(None, [_tool_call("move", "apply_journal_actions", actions=[{"type": "MOVE", "entryId": entry_id, "date": "yesterday"}])]),
        _text_reply("Moved the evidence meal."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(move_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="move it to yesterday")
        )
        await session.commit()

    undo_model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("Undone."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(undo_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        evidence = (await session.execute(select(NutritionEvidence).where(NutritionEvidence.food_entry_id == entry_id))).scalar_one()
        item = (await session.execute(select(FoodItem).where(FoodItem.id == evidence.food_item_id))).scalar_one()
        assert entry.eaten_at == original_when
        assert evidence.food_item_id == item.id
        assert evidence.total_calories == 200


@pytest.mark.asyncio
async def test_delete_is_soft_and_undo_restores_it():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 333, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    model1 = ScriptedModel([
        AgentReply(None, [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "gustare", "calories": 150}])]),
        _text_reply("Notat: gustare — 150 kcal."),
    ])
    agent1 = JournalAgent(model1, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await agent1.run(session, AgentContext(user=user, chat_id="1", message="gustare 150 kcal"))
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry_id = entry.id

    model2 = ScriptedModel([
        AgentReply(None, [_tool_call("c2", "apply_journal_actions", actions=[{"type": "DELETE", "entryId": entry_id}])]),
        _text_reply("Șters: gustare (150 kcal)."),
    ])
    agent2 = JournalAgent(model2, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply = await agent2.run(session, AgentContext(user=user, chat_id="1", message="sterge gustarea"))
        await session.commit()
    assert "gustare" in reply.lower()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.deleted_at is not None
        user = await _reload_user(session, user_id)
        found_active = await food_entry_repo.find_by_id_and_user(session, entry_id, user)
        assert found_active is None  # soft-deleted rows are excluded by default

    model3 = ScriptedModel([
        AgentReply(None, [_tool_call("c3", "undo_last_change")]),
        _text_reply("Anulat: ștergerea gustare (150 kcal)."),
    ])
    agent3 = JournalAgent(model3, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await agent3.run(session, AgentContext(user=user, chat_id="1", message="undo"))
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.deleted_at is None


@pytest.mark.asyncio
async def test_create_edit_delete_and_undo_mark_the_pinned_total_dirty_inside_message_execution():
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 334, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    async def run_action(tool_id, action):
        model = ScriptedModel([
            AgentReply(None, [_tool_call(tool_id, "apply_journal_actions", actions=[action])]),
            _text_reply("Done."),
        ])
        tools = JournalToolExecutor(refresh_daily_status=daily_status_service.refresh_for_tool_executor)
        agent = JournalAgent(model, tools, max_tool_calls=10)
        async with session_scope() as session:
            user = await _reload_user(session, user_id)
            await execution_context.run(lambda: agent.run(session, AgentContext(user=user, chat_id="334", message="update")))
            await session.commit()

    await run_action("create", {"type": "CREATE", "description": "meal", "calories": 100})
    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry_id = entry.id
        pinned = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user_id))).scalar_one()
        assert pinned.desired_version == 1 and "100 kcal" in pinned.desired_text

    await run_action("edit", {"type": "EDIT", "entryId": entry_id, "calories": 250})
    await run_action("delete", {"type": "DELETE", "entryId": entry_id})

    model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("Undone."),
    ])
    tools = JournalToolExecutor(refresh_daily_status=daily_status_service.refresh_for_tool_executor)
    agent = JournalAgent(model, tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await execution_context.run(lambda: agent.run(session, AgentContext(user=user, chat_id="334", message="undo")))
        await session.commit()

    async with session_scope() as session:
        pinned = (await session.execute(select(PinnedDailyStatus).where(PinnedDailyStatus.user_id == user_id))).scalar_one()
        assert pinned.desired_version == 4
        assert pinned.delivered_version == 0
        assert "250 kcal" in pinned.desired_text


@pytest.mark.asyncio
async def test_pinned_status_failure_does_not_roll_back_journal_mutation():
    async def fail_refresh(session, user, chat_id):
        raise RuntimeError("simulated pinned status failure")

    model = ScriptedModel([
        AgentReply(
            None,
            [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "description": "status safe", "calories": 321}])],
        ),
        _text_reply("Logged status safe."),
    ])
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 567, "Tester", "Europe/Bucharest")
        await session.commit()
        tools = JournalToolExecutor(refresh_daily_status=fail_refresh)
        result = await JournalAgent(model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="status safe")
        )
        await session.commit()

    assert "Logged status safe" in result
    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.original_message == "status safe"))).scalars().all()
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_invalid_calories_are_retried_by_the_model_instead_of_surfaced_raw():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "orez", "calories": 999999}])],
            ),
            AgentReply(
                None,
                [_tool_call("c2", "apply_journal_actions", actions=[{"type": "CREATE", "description": "orez", "calories": 650}])],
            ),
            _text_reply("Logged: orez — 650 kcal."),
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 556, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="orez 50g"))
        await session.commit()

    assert model.calls == 3
    assert "orez" in reply
    assert "650" in reply
    assert "Calories must be" not in reply

    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert len(entries) == 1
    assert entries[0].calories == 650


@pytest.mark.asyncio
async def test_mixed_batch_model_writes_receipt_without_retrying():
    """v2.0: A partial failure must not re-loop the model to retry the batch.
    The model writes a receipt from the structured result on the next turn.
    The system prompt tells it not to resend the batch."""
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [
                    _tool_call(
                        "c1",
                        "apply_journal_actions",
                        actions=[
                            {"type": "CREATE", "description": "supa", "calories": 200},
                            {"type": "CREATE", "description": "prajitura", "calories": 999999},
                        ],
                    )
                ],
            ),
            _text_reply("Notat: supa — 200 kcal. prajitura a eșuat: calories invalid."),
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 557, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="supa 200 kcal si prajitura"))
        await session.commit()

    assert model.calls == 2  # tool call + text reply
    assert "supa" in reply
    assert "200" in reply

    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert len(entries) == 1
    assert entries[0].calories == 200


@pytest.mark.asyncio
async def test_update_settings_validation_is_atomic():
    executor = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 560, "Tester", "Europe/Bucharest")
        settings = await session.get(UserSettings, user.id)
        original_timezone = settings.timezone
        await session.commit()

        no_op = await executor.execute(
            session,
            AgentContext(user=user, chat_id="1", message="update settings"),
            _tool_call("settings-no-op", "update_settings"),
            [],
        )
        assert not no_op.ok

        result = await executor.execute(
            session,
            AgentContext(user=user, chat_id="1", message="update settings"),
            _tool_call("settings", "update_settings", timezone="UTC", calorieTarget=1),
            [],
        )
        assert not result.ok
        await session.commit()

    async with session_scope() as session:
        settings = await session.get(UserSettings, user.id)
        assert settings.timezone == original_timezone


@pytest.mark.asyncio
async def test_malformed_action_type_is_reported_without_aborting_successful_actions():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [
                    _tool_call(
                        "c1",
                        "apply_journal_actions",
                        actions=[
                            {"type": "CREATE", "description": "valid meal", "calories": 200},
                            {"type": 1, "description": "malformed meal", "calories": 300},
                        ],
                    )
                ],
            ),
            _text_reply("Logged the valid meal; the malformed action was rejected."),
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 559, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="mixed malformed batch"))
        await session.commit()

    assert "valid meal" in reply
    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert len(entries) == 1
    assert entries[0].calories == 200


@pytest.mark.asyncio
async def test_oversized_create_description_is_reported_as_validation_failure():
    model = ScriptedModel(
        [
            AgentReply(
                None,
                [_tool_call("c1", "apply_journal_actions", actions=[{"type": "CREATE", "description": "x" * 256, "calories": 200}])],
            ),
            _text_reply("The description was too long."),
        ]
    )
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 561, "Tester", "Europe/Bucharest")
        await session.commit()
        await agent.run(session, AgentContext(user=user, chat_id="1", message="long description"))
        await session.commit()

    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert entries == []


@pytest.mark.asyncio
async def test_hits_the_max_tool_call_limit():
    tool_calls = [_tool_call(f"c{i}", "get_today_summary") for i in range(5)]
    model = ScriptedModel([AgentReply(None, tool_calls)])
    tools = JournalToolExecutor()
    agent = JournalAgent(model, tools, max_tool_calls=2)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 444, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="anything"))
    assert "detail" in reply.lower()


@pytest.mark.asyncio
async def test_model_failure_returns_graceful_unavailable_reply():
    tools = JournalToolExecutor()
    agent = JournalAgent(FailingModel(), tools, max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 555, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="hi"))
    assert "cannot process" in reply


@pytest.mark.asyncio
async def test_receipt_provider_failure_returns_structured_fallback_without_duplicate_retry():
    call = _tool_call(
        "create",
        "apply_journal_actions",
        actions=[{"type": "CREATE", "description": "fallback meal", "calories": 425}],
    )
    model = FailingAfterToolModel(call)
    agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 558, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await agent.run(session, AgentContext(user=user, chat_id="1", message="fallback meal"))
        await session.commit()

    assert model.calls == 2
    assert "fallback meal" in reply
    assert "425" in reply
    assert "Undo" in reply
    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user.id))).scalars().all()
    assert len(entries) == 1
    assert entries[0].calories == 425


@pytest.mark.asyncio
async def test_undo_expiry_race_is_reported_as_a_handled_tool_failure(monkeypatch):
    class ExpiringChangeSet:
        def __init__(self):
            self.id = 999999
            self.mutations = []

        def is_undoable_at(self, now):
            return True

        def mark_undone(self, now):
            raise ValueError("This change set can no longer be undone.")

    async def find_expiring_change_set(session, user, now):
        return ExpiringChangeSet()

    monkeypatch.setattr(
        "app.tools.journal_actions.journal_change_set_repo.find_first_undoable",
        find_expiring_change_set,
    )
    model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("The latest journal change can no longer be undone."),
    ])
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 565, "Tester", "Europe/Bucharest")
        await session.commit()
        reply = await JournalAgent(model, JournalToolExecutor(), max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    assert "can no longer be undone" in reply
    assert model.calls == 2


@pytest.mark.asyncio
async def test_undo_uses_execution_time_not_request_start_time(monkeypatch):
    observed: list[datetime] = []

    async def find_no_change(session, user, now):
        observed.append(now)

    monkeypatch.setattr(
        "app.tools.journal_actions.journal_change_set_repo.find_first_undoable",
        find_no_change,
    )
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 566, "Tester", "Europe/Bucharest")
        await session.commit()
        started_at = datetime.now(UTC) - timedelta(minutes=11)
        result = await JournalToolExecutor().execute(
            session,
            AgentContext(user=user, chat_id="1", message="undo", started_at=started_at),
            _tool_call("undo", "undo_last_change"),
            [],
        )

    assert not result.ok
    assert result.code == "NOT_FOUND"
    assert observed
    assert observed[0] > started_at + timedelta(minutes=10)


@pytest.mark.asyncio
async def test_undo_refuses_to_overwrite_an_intervening_entry_change():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 562, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    create_model = ScriptedModel([
        AgentReply(None, [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "description": "original", "calories": 200}])]),
        _text_reply("Logged original."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(create_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="original")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry.revise("intervening change", 999)
        await session.commit()

    undo_model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("The change could not be undone safely."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        reply = await JournalAgent(undo_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    assert "could not be undone" in reply
    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        assert entry.original_message == "intervening change"
        assert entry.calories == 999


@pytest.mark.asyncio
async def test_undo_handles_multiple_mutations_of_the_same_entry_in_one_batch():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 563, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    create_model = ScriptedModel([
        AgentReply(None, [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "description": "same entry", "calories": 200}])]),
        _text_reply("Logged same entry."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(create_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="same entry")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        entry_id = entry.id
        original_when = entry.eaten_at

    update_model = ScriptedModel([
        AgentReply(
            None,
            [_tool_call(
                "update",
                "apply_journal_actions",
                actions=[
                    {"type": "EDIT", "entryId": entry_id, "description": "edited entry", "calories": 300},
                    {"type": "MOVE", "entryId": entry_id, "date": "yesterday"},
                ],
            )],
        ),
        _text_reply("Updated same entry."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(update_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="edit and move")
        )
        await session.commit()

    undo_model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("Undone."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(undo_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        assert entry.original_message == "same entry"
        assert entry.calories == 200
        assert entry.eaten_at == original_when


@pytest.mark.asyncio
async def test_journal_mutations_serialize_per_user_before_undo_selects_latest_change():
    tools = JournalToolExecutor()
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 564, "Tester", "Europe/Bucharest")
        user_id = user.id
        await session.commit()

    create_model = ScriptedModel([
        AgentReply(None, [_tool_call("initial", "apply_journal_actions", actions=[{"type": "CREATE", "description": "initial", "calories": 100}])]),
        _text_reply("Logged initial."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(create_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="initial")
        )
        await session.commit()

    async def create_concurrent_entry() -> None:
        model = ScriptedModel([
            AgentReply(None, [_tool_call("concurrent", "apply_journal_actions", actions=[{"type": "CREATE", "description": "concurrent", "calories": 200}])]),
            _text_reply("Logged concurrent."),
        ])
        async with session_scope() as session:
            user = await _reload_user(session, user_id)
            await JournalAgent(model, tools, max_tool_calls=10).run(
                session, AgentContext(user=user, chat_id="1", message="concurrent")
            )
            await session.commit()

    async with session_scope() as holder:
        await food_user_repo.lock_for_journal_mutation(holder, user_id)
        concurrent_task = asyncio.create_task(create_concurrent_entry())
        await asyncio.sleep(0.1)
        assert not concurrent_task.done()
        await holder.commit()
        await asyncio.wait_for(concurrent_task, timeout=5)

    async with session_scope() as session:
        entries = (
            await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id).order_by(FoodEntry.id))
        ).scalars().all()
        assert [entry.original_message for entry in entries] == ["initial", "concurrent"]

    undo_model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("Undone."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(undo_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    async with session_scope() as session:
        entries = (
            await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id).order_by(FoodEntry.id))
        ).scalars().all()
        assert entries[0].deleted_at is None
        assert entries[1].deleted_at is not None


@pytest.mark.asyncio
async def test_new_change_set_undo_window_starts_when_mutation_executes():
    model = ScriptedModel([
        AgentReply(
            None,
            [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "description": "slow meal", "calories": 150}])],
        ),
        _text_reply("Logged slow meal."),
    ])
    started_at = datetime.now(UTC) - timedelta(minutes=11)

    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 5678, "Tester", "Europe/Bucharest")
        await session.commit()
        await JournalAgent(model, JournalToolExecutor(), max_tool_calls=10).run(
            session,
            AgentContext(user=user, chat_id="1", message="slow meal", started_at=started_at),
        )
        await session.commit()
        change_set = (
            await session.execute(
                select(JournalChangeSet).where(JournalChangeSet.user_id == user.id)
            )
        ).scalar_one()

    assert change_set.created_at > started_at + timedelta(minutes=10)
    assert change_set.expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_ai_estimate_evidence_survives_edit_and_undo():
    tools = JournalToolExecutor()
    now = datetime.now(UTC)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 5680, "Tester", "Europe/Bucharest")
        quote = PendingNutritionQuote(
            quote_id=uuid.uuid4(), batch_id=uuid.uuid4(), user_id=user.id, quote_type="AI_ESTIMATE",
            product_name="estimated curry", grams=Decimal("250.00"), calories_per_100g=200,
            estimate_basis="visible bowl portion", created_at=now, expires_at=now + timedelta(minutes=30),
        )
        session.add(quote)
        quote_id = quote.quote_id
        user_id = user.id
        await session.commit()

    create_model = ScriptedModel([
        AgentReply(None, [_tool_call("create", "apply_journal_actions", actions=[{"type": "CREATE", "quoteId": str(quote_id)}])]),
        _text_reply("Prepared and logged estimated curry."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(create_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="log the estimate")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.user_id == user_id))).scalar_one()
        evidence = (await session.execute(select(NutritionEvidence).where(NutritionEvidence.food_entry_id == entry.id))).scalar_one()
        assert evidence.provider == "ai_estimate"
        assert evidence.selected_quote_id == quote_id
        assert evidence.source_name == "AI estimate"
        entry_id = entry.id

    edit_model = ScriptedModel([
        AgentReply(None, [_tool_call("edit", "apply_journal_actions", actions=[{"type": "EDIT", "entryId": entry_id, "calories": 450}])]),
        _text_reply("Updated estimated curry."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(edit_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="adjust estimate")
        )
        await session.commit()

    undo_model = ScriptedModel([
        AgentReply(None, [_tool_call("undo", "undo_last_change")]),
        _text_reply("Undone."),
    ])
    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        await JournalAgent(undo_model, tools, max_tool_calls=10).run(
            session, AgentContext(user=user, chat_id="1", message="undo")
        )
        await session.commit()

    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        evidence = (await session.execute(select(NutritionEvidence).where(NutritionEvidence.food_entry_id == entry_id))).scalar_one()
        assert entry.calories == 500
        assert evidence.provider == "ai_estimate"
        assert evidence.selected_quote_id == quote_id
        assert evidence.derivation == "250.00 g × 200 kcal/100 g = 500 kcal"


@pytest.mark.asyncio
async def test_malformed_undo_snapshot_returns_conflict_without_mutating_state():
    now = datetime.now(UTC)
    async with session_scope() as session:
        user = await get_or_create_by_telegram_user_id(session, 5690, "Tester", "Europe/Bucharest")
        entry = FoodEntry(
            user_id=user.id,
            original_message="snapshot meal",
            eaten_at=now,
            calories=200,
            nutrition_source="manual",
            confidence="high",
            created_at=now,
        )
        session.add(entry)
        await session.flush()

        change_set = JournalChangeSet(
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(minutes=10),
        )
        change_set.add_mutation(
            "EDIT",
            {"entryId": entry.id},
            {
                "entryId": entry.id,
                "originalMessage": entry.original_message,
                "eatenAt": entry.eaten_at.isoformat(),
                "calories": entry.calories,
                "nutritionSource": entry.nutrition_source,
                "confidence": entry.confidence,
                "deletedAt": None,
                "items": [],
            },
        )
        session.add(change_set)
        await session.commit()
        user_id = user.id
        entry_id = entry.id

    async with session_scope() as session:
        user = await _reload_user(session, user_id)
        result = await JournalToolExecutor().execute(
            session,
            AgentContext(user=user, chat_id="1", message="undo"),
            _tool_call("undo", "undo_last_change"),
            [],
        )
        await session.commit()

    assert not result.ok
    assert result.code == "CONFLICT"
    async with session_scope() as session:
        entry = (await session.execute(select(FoodEntry).where(FoodEntry.id == entry_id))).scalar_one()
        change_set = (
            await session.execute(select(JournalChangeSet).where(JournalChangeSet.user_id == user_id))
        ).scalar_one()
        assert entry.original_message == "snapshot meal"
        assert entry.calories == 200
        assert change_set.undone_at is None
