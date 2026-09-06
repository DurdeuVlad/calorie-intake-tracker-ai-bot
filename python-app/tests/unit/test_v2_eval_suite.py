"""Unit tests for the v2.0 evaluation fixture suite (issue #109).

Validates that the fixture file is well-formed JSON, contains the expected v2.0
scenarios, and that every scenario has valid assertion types and categories.
This is a static structural check -- the live eval runner exercises the model
against these scenarios with real OpenAI calls."""

import json
from pathlib import Path

from app.terminal.eval_runner import read_fixture
from app.terminal.eval_scorer import Category

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "app" / "terminal" / "fixtures" / "text-journal.json"

VALID_ASSERTION_TYPES = {
    "tool_required",
    "tool_forbidden",
    "tool_outcome",
    "entries_exact",
    "entries_at_least",
    "entries_at_most",
    "reply_contains_any",
    "reply_not_contains",
}

VALID_CATEGORIES = {c.name for c in Category}

V2_SCENARIO_IDS = {
    "v2-weekly-summary",
    "v2-food-history-search",
    "v2-custom-alias-save-and-use",
    "v2-mixed-language-reply",
    "v2-progressive-disclosure-load-instructions",
    "v2-no-template-artifacts-in-reply",
}


def test_fixture_file_is_valid_json_and_parseable():
    fixture = read_fixture(str(FIXTURE_PATH))
    assert fixture.version
    assert len(fixture.scenarios) >= 10


def test_fixture_file_raw_json_is_well_formed():
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert "version" in data
    assert "scenarios" in data
    assert isinstance(data["scenarios"], list)
    for scenario in data["scenarios"]:
        assert "id" in scenario
        assert "turns" in scenario
        for turn in scenario["turns"]:
            assert "input" in turn
            assert "assertions" in turn
            for assertion in turn["assertions"]:
                assert "category" in assertion
                assert "type" in assertion
                assert assertion["category"] in VALID_CATEGORIES
                assert assertion["type"] in VALID_ASSERTION_TYPES


def test_v2_scenarios_are_present():
    fixture = read_fixture(str(FIXTURE_PATH))
    scenario_ids = {s.id for s in fixture.scenarios}
    missing = V2_SCENARIO_IDS - scenario_ids
    assert not missing, f"Missing v2.0 eval scenarios: {missing}"


def test_v2_weekly_summary_scenario_requires_get_weekly_summary_tool():
    fixture = read_fixture(str(FIXTURE_PATH))
    scenario = next(s for s in fixture.scenarios if s.id == "v2-weekly-summary")
    has_tool_assertion = any(
        a.type == "tool_required" and a.tool == "get_weekly_summary"
        for turn in scenario.turns
        for a in turn.assertions
    )
    assert has_tool_assertion


def test_v2_food_history_scenario_requires_search_food_history_tool():
    fixture = read_fixture(str(FIXTURE_PATH))
    scenario = next(s for s in fixture.scenarios if s.id == "v2-food-history-search")
    has_tool_assertion = any(
        a.type == "tool_required" and a.tool == "search_food_history"
        for turn in scenario.turns
        for a in turn.assertions
    )
    assert has_tool_assertion


def test_v2_alias_scenario_requires_save_and_resolve_tools():
    fixture = read_fixture(str(FIXTURE_PATH))
    scenario = next(s for s in fixture.scenarios if s.id == "v2-custom-alias-save-and-use")
    tools_required = {
        a.tool for turn in scenario.turns for a in turn.assertions if a.type == "tool_required"
    }
    assert "save_alias" in tools_required
    assert "resolve_alias" in tools_required


def test_v2_no_template_artifacts_scenario_checks_reply_quality():
    fixture = read_fixture(str(FIXTURE_PATH))
    scenario = next(s for s in fixture.scenarios if s.id == "v2-no-template-artifacts-in-reply")
    has_reply_not_contains = any(
        a.type == "reply_not_contains" and a.values
        for turn in scenario.turns
        for a in turn.assertions
    )
    assert has_reply_not_contains


def test_every_v2_scenario_has_at_least_one_safety_assertion():
    fixture = read_fixture(str(FIXTURE_PATH))
    for scenario in fixture.scenarios:
        if not scenario.id.startswith("v2-"):
            continue
        has_safety = any(
            a.category == Category.SAFETY.name for turn in scenario.turns for a in turn.assertions
        )
        assert has_safety, f"Scenario {scenario.id} has no SAFETY assertions"


def test_v2_scenarios_have_critical_safety_assertions():
    fixture = read_fixture(str(FIXTURE_PATH))
    for scenario_id in V2_SCENARIO_IDS:
        scenario = next(s for s in fixture.scenarios if s.id == scenario_id)
        has_critical_safety = any(
            a.category == Category.SAFETY.name and a.critical
            for turn in scenario.turns
            for a in turn.assertions
        )
        # Scenarios that don't create entries still should have a critical safety check
        # (e.g. entries_exact=0). Alias scenarios are an exception since they don't
        # touch journal entries -- they have non-critical safety assertions.
        if scenario_id != "v2-custom-alias-save-and-use":
            assert has_critical_safety, f"Scenario {scenario_id} has no critical SAFETY assertion"
