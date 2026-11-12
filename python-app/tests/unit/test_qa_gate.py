import json

import httpx
import pytest

from app.agent.journal_agent import JournalAgent
from app.agent.qa_gate import PlausibilityJudge, QaVerdict
from app.config import Settings
from app.domain.agent_types import AgentContext, AgentReply
from app.services.journal_tool_executor import JournalToolExecutor


def _context():
    return AgentContext(user=None, chat_id="1", message="10 KFC wings")


class ScriptedModel:
    def __init__(self):
        self.seen_notes = []

    async def next(self, context, memory, exchanges, feedback=None, qa_notes=None):
        self.seen_notes.append(list(qa_notes or []))
        return AgentReply(f"draft {len(self.seen_notes)}", [])


class ScriptedJudge:
    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = 0

    async def review(self, context, exchanges, reply):
        self.calls += 1
        return self.verdicts.pop(0)


def _agent(model, judge):
    return JournalAgent(model, JournalToolExecutor(), max_tool_calls=10, qa=judge)


@pytest.mark.asyncio
async def test_plausible_reply_passes_with_one_review():
    model, judge = ScriptedModel(), ScriptedJudge([QaVerdict(True)])
    assert await _agent(model, judge).run(None, _context()) == "draft 1"
    assert judge.calls == 1 and model.seen_notes == [[]]


@pytest.mark.asyncio
async def test_rejection_retries_model_with_issue_then_accepts():
    model, judge = ScriptedModel(), ScriptedJudge([QaVerdict(False, "25 kcal for 10 wings"), QaVerdict(True)])
    assert await _agent(model, judge).run(None, _context()) == "draft 2"
    assert "25 kcal for 10 wings" in model.seen_notes[1][0]


@pytest.mark.asyncio
async def test_at_most_two_retries_per_request():
    model = ScriptedModel()
    judge = ScriptedJudge([QaVerdict(False, "bad"), QaVerdict(False, "still bad"), QaVerdict(False, "never asked")])
    assert await _agent(model, judge).run(None, _context()) == "draft 3"
    assert judge.calls == 2 and len(model.seen_notes) == 3


def _judge(handler):
    settings = Settings(OPENAI_API_KEY="k")
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://x")
    return PlausibilityJudge(settings, http)


def _reply(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@pytest.mark.asyncio
async def test_judge_parses_rejection():
    judge = _judge(lambda r: _reply(json.dumps({"plausible": False, "issues": "too low"})))
    assert await judge.review(_context(), [], "3 kcal") == QaVerdict(False, "too low")


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [
    lambda r: httpx.Response(500),
    lambda r: _reply("not json"),
    lambda r: _reply(json.dumps({"plausible": "no"})),
])
async def test_judge_fails_open(handler):
    assert (await _judge(handler).review(_context(), [], "x")).plausible is True
