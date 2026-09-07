from datetime import datetime
from zoneinfo import ZoneInfo

from app.repositories.food_entry_repo import day_bounds, local_tracking_date

_ZONE = ZoneInfo("Europe/Bucharest")


def test_default_boundary_hour_matches_calendar_midnight():
    now = datetime(2026, 9, 2, 1, 30, tzinfo=_ZONE)
    assert local_tracking_date(now, _ZONE) == now.date()

    start, end = day_bounds(now.date(), _ZONE)
    assert start == datetime(2026, 9, 2, 0, 0, tzinfo=_ZONE)
    assert end == datetime(2026, 9, 3, 0, 0, tzinfo=_ZONE)


def test_a_snack_before_the_boundary_hour_belongs_to_the_previous_tracking_day():
    """The whole point of this feature: with a 4am boundary, a 2am snack is
    still "yesterday", not a fresh new tracking day."""
    two_am = datetime(2026, 9, 2, 2, 0, tzinfo=_ZONE)
    assert local_tracking_date(two_am, _ZONE, boundary_hour=4) == datetime(2026, 9, 1).date()


def test_a_moment_at_or_after_the_boundary_hour_belongs_to_the_new_tracking_day():
    four_am = datetime(2026, 9, 2, 4, 0, tzinfo=_ZONE)
    assert local_tracking_date(four_am, _ZONE, boundary_hour=4) == datetime(2026, 9, 2).date()


def test_day_bounds_with_a_custom_boundary_hour_spans_boundary_to_boundary():
    start, end = day_bounds(datetime(2026, 9, 2).date(), _ZONE, boundary_hour=4)
    assert start == datetime(2026, 9, 2, 4, 0, tzinfo=_ZONE)
    assert end == datetime(2026, 9, 3, 4, 0, tzinfo=_ZONE)


def test_local_tracking_date_normalizes_from_a_different_input_timezone():
    utc = ZoneInfo("UTC")
    # 2026-09-02 01:00 UTC is 2026-09-02 04:00 Europe/Bucharest (UTC+3 in September).
    moment = datetime(2026, 9, 2, 1, 0, tzinfo=utc)
    assert local_tracking_date(moment, _ZONE, boundary_hour=4) == datetime(2026, 9, 2).date()
    # One minute earlier crosses back to the previous tracking day.
    moment_before = datetime(2026, 9, 2, 0, 59, tzinfo=utc)
    assert local_tracking_date(moment_before, _ZONE, boundary_hour=4) == datetime(2026, 9, 1).date()
