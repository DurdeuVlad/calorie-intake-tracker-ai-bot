"""Integration tests for the terminal REPL/eval harness (TerminalConversation +
eval_runner), using a scripted model instead of a real OpenAI call -- the same
substitution pattern as test_journal_agent_apply_actions.py."""

import json

import pytest

from app.agent.journal_agent import JournalAgent
from app.config import TerminalSettings, get_settings
from app.domain.agent_types import AgentReply, ToolCall
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging.inbox_worker import InboxWorkerDeps
from app.services.journal_application_service import JournalApplicationService
from app.services.journal_tool_executor import JournalToolExecutor
from app.terminal import eval_runner
from app.terminal.conversation import TerminalConversation
from app.terminal.terminal_frontend import TerminalFrontend
from app.terminal.trace_collector import TerminalTraceCollector

TERMINAL_USER_ID = 777


class ScriptedModel:
    """Returns one AgentReply per call to next(), in order."""

    def __init__(self, replies: list[AgentReply]) -> None:
        self._replies = list(replies)
        self.calls = 0

    async def next(self, context, memory, exchanges):
        reply = self._replies[self.calls]
        self.calls += 1
        return reply


@pytest.fixture(autouse=True)
def _allow_terminal_user(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(type(settings), "allowed_telegram_user_id_set", property(lambda self: {str(TERMINAL_USER_ID)}))
    yield


def _build_chat(replies: list[AgentReply]):
    traces = TerminalTraceCollector()
    model = ScriptedModel(replies)
    tools = JournalToolExecutor()
    agent = JournalAgent(model, tools, max_tool_calls=10, trace=traces)
    journal = JournalApplicationService("Europe/Bucharest", agent=agent)
    terminal_frontend = TerminalFrontend()
    registry = FrontendRegistry([terminal_frontend])
    deps = InboxWorkerDeps(journal=journal, frontends=registry)
    settings = get_settings()
    chat = TerminalConversation(settings, deps, registry, terminal_frontend, traces, TERMINAL_USER_ID, "Tester")
    return chat, traces


@pytest.mark.asyncio
async def test_terminal_conversation_round_trips_a_plain_reply():
    chat, _ = _build_chat([AgentReply("Salut!", [])])
    result = await chat.send("buna")
    assert result.reply == "Salut!"
    assert result.trace is not None
    assert result.trace.model_turns == 1
    assert result.trace.tools == []


@pytest.mark.asyncio
async def test_terminal_conversation_rejects_a_user_id_outside_the_allowlist():
    traces = TerminalTraceCollector()
    tools = JournalToolExecutor()
    agent = JournalAgent(ScriptedModel([]), tools, max_tool_calls=10, trace=traces)
    journal = JournalApplicationService("Europe/Bucharest", agent=agent)
    terminal_frontend = TerminalFrontend()
    registry = FrontendRegistry([terminal_frontend])
    deps = InboxWorkerDeps(journal=journal, frontends=registry)
    settings = get_settings()
    with pytest.raises(ValueError, match="ALLOWED_TELEGRAM_USER_IDS"):
        TerminalConversation(settings, deps, registry, terminal_frontend, traces, 999999, "Nobody")


@pytest.mark.asyncio
async def test_eval_runner_scores_a_passing_fixture_and_writes_a_report(tmp_path):
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "version": "test-1",
                "scenarios": [
                    {
                        "id": "greet",
                        "turns": [
                            {
                                "input": "hello",
                                "assertions": [
                                    {"category": "CONVERSATION", "type": "reply_contains_any", "values": ["hi", "hello", "salut"]},
                                    {"category": "SAFETY", "critical": True, "type": "entries_exact", "value": 0},
                                    {"category": "TOOL_CORRECTNESS", "type": "tool_forbidden", "tool": "apply_journal_actions"},
                                    {"category": "REPLY_QUALITY", "type": "reply_not_contains", "values": ["error"]},
                                ],
                            }
                        ],
                    }
                ],
            }
        )
    )
    report_path = tmp_path / "report.json"
    terminal = TerminalSettings(user_id=TERMINAL_USER_ID, display_name="Tester", eval_repeats=2, report_file=str(report_path))

    # Two repeats x one turn each = two sequential model calls.
    chat, _ = _build_chat([AgentReply("Salut acolo!", []), AgentReply("Hello there!", [])])
    settings = get_settings()

    exit_code = await eval_runner.run(str(fixture_path), chat, settings, terminal)

    assert exit_code == 0
    report = json.loads(report_path.read_text())
    assert report["score"]["qualityScore"] == 100.0
    assert report["score"]["safetyReleasePassed"] is True
    assert report["userOutcomes"]["scenarioRuns"] == 2
    assert report["userOutcomes"]["crossScenarioLeakage"] == 0


@pytest.mark.asyncio
async def test_eval_runner_caps_score_on_critical_failure_and_returns_nonzero_exit(tmp_path):
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "version": "test-1",
                "scenarios": [
                    {
                        "id": "no-entries-expected",
                        "turns": [
                            {
                                "input": "am mancat pui",
                                "assertions": [{"category": "SAFETY", "critical": True, "type": "entries_exact", "value": 0}],
                            }
                        ],
                    }
                ],
            }
        )
    )
    report_path = tmp_path / "report.json"
    terminal = TerminalSettings(user_id=TERMINAL_USER_ID, display_name="Tester", eval_repeats=1, report_file=str(report_path))

    # apply_journal_actions is a canonical short-circuit -- one model call creates
    # an entry and the reply is rendered deterministically, no second model call.
    tool_call_reply = AgentReply(
        None,
        [
            ToolCall(
                id="c1",
                name="apply_journal_actions",
                arguments=json.dumps({"actions": [{"type": "CREATE", "description": "pui", "calories": 300}]}),
            )
        ],
    )
    chat, _ = _build_chat([tool_call_reply])
    settings = get_settings()

    exit_code = await eval_runner.run(str(fixture_path), chat, settings, terminal)

    assert exit_code == 1
    report = json.loads(report_path.read_text())
    assert report["score"]["qualityScore"] <= 59.0
    assert report["score"]["safetyReleasePassed"] is False
