"""Europe/Bucharest DST transitions (EU rule: last Sunday of March 02:00->03:00
spring-forward gap; last Sunday of October 04:00->03:00 fall-back ambiguity).
_resolve_meal_instant must reject a gap and pick the FIRST (earlier, still-DST)
offset for an ambiguous hour, matching Java's ZoneRules.getValidOffsets().getFirst()."""

from datetime import datetime, timezone

import pytest

from app.domain.agent_types import AgentContext
from app.db.models.users import FoodUser
from app.services.journal_tool_executor import ValidationError, _resolve_meal_instant


def _context(started_at: datetime) -> AgentContext:
    user = FoodUser(id=1, telegram_user_id=1, display_name="Tester", created_at=started_at)
    return AgentContext(user=user, chat_id="1", romanian=False, message="test", started_at=started_at)


def test_rejects_a_nonexistent_local_time_in_the_spring_forward_gap():
    # 2026-03-29 is the last Sunday of March; EU clocks jump 03:00 -> 04:00 EEST,
    # so local times in [03:00, 04:00) never occur.
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    context = _context(started_at)
    with pytest.raises(ValidationError, match="daylight-saving"):
        _resolve_meal_instant(context, "Europe/Bucharest", "2026-03-29", "03:30")


def test_accepts_a_normal_time_shortly_before_the_gap():
    started_at = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    context = _context(started_at)
    result = _resolve_meal_instant(context, "Europe/Bucharest", "2026-03-29", "02:30")
    assert result is not None


def test_ambiguous_fall_back_hour_resolves_to_the_first_earlier_offset():
    # 2026-10-25 is the last Sunday of October; 03:00-04:00 local occurs twice
    # (once at UTC+3 DST, once at UTC+2 standard). The first (DST) offset wins.
    started_at = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    context = _context(started_at)
    result = _resolve_meal_instant(context, "Europe/Bucharest", "2026-10-25", "03:30")
    # UTC+3 (DST/EEST) interpretation -> 00:30 UTC, not UTC+2 (EET) -> 01:30 UTC.
    assert result.hour == 0
    assert result.minute == 30


def test_rejects_a_future_meal_time():
    started_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    context = _context(started_at)
    with pytest.raises(ValidationError, match="Future meal"):
        _resolve_meal_instant(context, "Europe/Bucharest", "2026-01-02", None)
