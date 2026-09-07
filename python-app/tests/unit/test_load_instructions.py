"""Unit tests for the load_instructions tool (issue #102)."""

import json

import pytest

from app.domain.agent_types import AgentContext, ToolCall
from app.services.journal_tool_executor import JournalToolExecutor


def _context() -> AgentContext:
    return AgentContext(user=type("User", (), {"id": 1})(), chat_id="1", message="test")


@pytest.mark.asyncio
async def test_load_instructions_returns_nutrition_rules():
    executor = JournalToolExecutor()
    call = ToolCall(id="1", name="load_instructions", arguments='{"topic": "nutrition"}')
    result = await executor.execute(None, _context(), call, [])
    assert result.ok
    assert result.data["topic"] == "nutrition"
    assert "search_web" in result.data["instructions"]
    assert "1 kcal" in result.data["instructions"]


@pytest.mark.asyncio
async def test_load_instructions_returns_portions_rules():
    executor = JournalToolExecutor()
    call = ToolCall(id="1", name="load_instructions", arguments='{"topic": "portions"}')
    result = await executor.execute(None, _context(), call, [])
    assert result.ok
    assert result.data["topic"] == "portions"
    assert "fraction" in result.data["instructions"].lower()
    # The doc must not reference tools that do not exist in the registry.
    from app.tools.registry import HANDLERS

    for word in result.data["instructions"].split():
        cleaned = word.strip("`.,:;()\"'")
        if cleaned and cleaned.isidentifier() and "_" in cleaned:
            if cleaned in {"save_alias", "resolve_alias", "load_instructions"}:
                continue
            assert cleaned in HANDLERS, f"portions.md references unknown tool: {cleaned}"


@pytest.mark.asyncio
async def test_load_instructions_returns_combos_rules():
    executor = JournalToolExecutor()
    call = ToolCall(id="1", name="load_instructions", arguments='{"topic": "combos"}')
    result = await executor.execute(None, _context(), call, [])
    assert result.ok
    assert "one CREATE" in result.data["instructions"]


@pytest.mark.asyncio
async def test_load_instructions_returns_editing_rules():
    executor = JournalToolExecutor()
    call = ToolCall(id="1", name="load_instructions", arguments='{"topic": "editing"}')
    result = await executor.execute(None, _context(), call, [])
    assert result.ok
    assert "absolute" in result.data["instructions"]


@pytest.mark.asyncio
async def test_load_instructions_returns_daily_totals_rules():
    executor = JournalToolExecutor()
    call = ToolCall(id="1", name="load_instructions", arguments='{"topic": "daily_totals"}')
    result = await executor.execute(None, _context(), call, [])
    assert result.ok
    assert "get_today_summary" in result.data["instructions"]


@pytest.mark.asyncio
async def test_load_instructions_returns_onboarding_rules():
    executor = JournalToolExecutor()
    call = ToolCall(id="1", name="load_instructions", arguments='{"topic": "onboarding"}')
    result = await executor.execute(None, _context(), call, [])
    assert result.ok
    assert "timezone" in result.data["instructions"].lower()


@pytest.mark.asyncio
async def test_load_instructions_returns_aliases_rules():
    executor = JournalToolExecutor()
    call = ToolCall(id="1", name="load_instructions", arguments='{"topic": "aliases"}')
    result = await executor.execute(None, _context(), call, [])
    assert result.ok
    assert result.data["topic"] == "aliases"
    assert "save_alias" in result.data["instructions"]
    assert "resolve_alias" in result.data["instructions"]


@pytest.mark.asyncio
async def test_load_instructions_rejects_invalid_topic():
    executor = JournalToolExecutor()
    call = ToolCall(id="1", name="load_instructions", arguments='{"topic": "nonexistent"}')
    result = await executor.execute(None, _context(), call, [])
    assert not result.ok
    assert result.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_load_instructions_rejects_missing_topic():
    executor = JournalToolExecutor()
    call = ToolCall(id="1", name="load_instructions", arguments="{}")
    result = await executor.execute(None, _context(), call, [])
    assert not result.ok
    assert result.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_executor_rejects_non_object_arguments():
    executor = JournalToolExecutor()
    call = ToolCall(id="1", name="load_instructions", arguments="[]")
    result = await executor.execute(None, _context(), call, [])
    assert not result.ok
    assert result.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_executor_rejects_wrong_argument_types():
    executor = JournalToolExecutor()
    call = ToolCall(id="1", name="load_instructions", arguments='{"topic": 1}')
    result = await executor.execute(None, _context(), call, [])
    assert not result.ok
    assert result.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_executor_rejects_deeply_nested_and_oversized_arguments():
    executor = JournalToolExecutor()
    deeply_nested = "[" * 5000 + "]" * 5000
    deep_result = await executor.execute(
        None, _context(), ToolCall(id="1", name="load_instructions", arguments=deeply_nested), []
    )
    oversized_result = await executor.execute(
        None,
        _context(),
        ToolCall(id="2", name="load_instructions", arguments="{" + "x" * (64 * 1024) + "}"),
        [],
    )

    assert not deep_result.ok and deep_result.code == "VALIDATION_ERROR"
    assert not oversized_result.ok and oversized_result.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_executor_rejects_integer_digit_limit_arguments():
    executor = JournalToolExecutor()
    arguments = '{"topic":' + ("9" * 5000) + "}"
    result = await executor.execute(None, _context(), ToolCall(id="1", name="load_instructions", arguments=arguments), [])
    assert not result.ok
    assert result.code == "VALIDATION_ERROR"


def test_tool_schemas_mirror_runtime_action_limits():
    from app.agent.tool_schemas import tool_definitions

    definitions = {tool["function"]["name"]: tool["function"] for tool in tool_definitions()}
    action = definitions["apply_journal_actions"]["parameters"]["properties"]["actions"]
    action_properties = action["items"]["properties"]

    assert action["maxItems"] == 20
    assert action_properties["description"]["maxLength"] == 255
    assert action_properties["entryId"]["minimum"] == 1
    assert action_properties["calories"]["minimum"] == 0
    assert action_properties["quantity"]["maximum"] == 100000.0
    assert action_properties["quantity"]["exclusiveMinimum"] == 0
    assert action_properties["quantity"]["multipleOf"] == 0.01
    resolver_properties = definitions["resolve_nutrition"]["parameters"]["properties"]
    assert resolver_properties["grams"]["multipleOf"] == 0.01
    assert resolver_properties["caloriesPer100g"]["minimum"] == 1
    assert "name" in action_properties
    assert definitions["search_entries"]["parameters"]["properties"]["query"]["maxLength"] == 255
    assert definitions["fetch_web_page"]["parameters"]["properties"]["url"]["maxLength"] == 2048
    assert definitions["plan_todos"]["parameters"]["properties"]["todos"]["items"]["maxLength"] == 255
    assert definitions["save_private_food"]["parameters"]["properties"]["name"]["maxLength"] == 255
    alias_properties = definitions["save_alias"]["parameters"]["properties"]
    assert alias_properties["caloriesPer100g"]["minimum"] == 1
    assert alias_properties["caloriesPer100g"]["maximum"] == 10000
    assert alias_properties["fixedCalories"]["minimum"] == 0
    assert alias_properties["fixedCalories"]["maximum"] == 10000
    assert definitions["update_settings"]["parameters"]["minProperties"] == 1
    assert definitions["resolve_alias"]["parameters"]["properties"]["alias"]["maxLength"] == 255


@pytest.mark.asyncio
async def test_executor_rejects_unknown_nested_argument_fields():
    executor = JournalToolExecutor()
    result = await executor.execute(
        None,
        _context(),
        ToolCall(
            id="1",
            name="apply_journal_actions",
            arguments=json.dumps({"actions": [{"type": "CREATE", "description": "meal", "calories": 100, "unexpected": True}]}),
        ),
        [],
    )
    assert not result.ok
    assert result.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_planning_rejects_non_text_and_oversized_steps():
    executor = JournalToolExecutor()
    todos: list[str] = []

    non_text = await executor.execute(
        None,
        _context(),
        ToolCall(id="1", name="plan_todos", arguments='{"todos": [1]}'),
        todos,
    )
    oversized = await executor.execute(
        None,
        _context(),
        ToolCall(id="2", name="plan_todos", arguments=json.dumps({"todos": ["x" * 256]})),
        todos,
    )

    assert not non_text.ok and non_text.code == "VALIDATION_ERROR"
    assert not oversized.ok and oversized.code == "VALIDATION_ERROR"
    assert todos == []
