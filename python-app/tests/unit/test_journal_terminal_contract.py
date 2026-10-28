"""An explicit unmet acceptance gate, not a passing safety claim."""
import pytest

from app.agent.journal_agent import JournalAgent
from app.domain.agent_types import AgentContext, AgentReply


class FalseSuccessModel:
    async def next(self, context, recent, exchanges, feedback):
        return AgentReply("Logged: imaginary meal — 321 kcal.", [])


class NoTools:
    async def execute(self, *args):
        raise AssertionError("No mutation was requested")


@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, reason="Unrestricted no-tool text lacks a structured terminal-reply evidence contract")
async def test_no_tool_false_success_must_not_be_delivered():
    reply = await JournalAgent(FalseSuccessModel(), NoTools(), 10).run(None, AgentContext(None, "1", "log my meal"))
    assert "Logged: imaginary meal" not in reply
