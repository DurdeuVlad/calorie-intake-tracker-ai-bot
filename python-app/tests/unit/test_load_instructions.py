"""Unit tests for the load_instructions tool (issue #102)."""

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
