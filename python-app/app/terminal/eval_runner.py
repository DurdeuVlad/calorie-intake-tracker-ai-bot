"""Opt-in real-model evaluation runner, ported from TerminalEvaluationRunner.java.
Deliberately outside pytest/CI -- it makes real OpenAI calls and is invoked manually
via `python -m app.terminal.repl` with TERMINAL_EVAL_FILE set."""

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, TerminalSettings
from app.db.models.conversation import ConversationMemory
from app.db.models.entries import FoodEntry
from app.db.models.messaging import MessagingInboxMessage, MessagingOutboundMessage
from app.db.models.nutrition import PendingNutritionQuote
from app.db.models.users import FoodUser
from app.terminal import eval_scorer
from app.terminal.conversation import TerminalConversation


@dataclass(frozen=True)
class Expectation:
    category: str
    type: str
    critical: bool = False
    tool: str | None = None
    outcome: str | None = None
    value: int | None = None
    values: list[str] | None = None


@dataclass(frozen=True)
class Turn:
    input: str
    assertions: list[Expectation] = field(default_factory=list)


@dataclass(frozen=True)
class Scenario:
    id: str
    turns: list[Turn]
    start_onboarded: bool = False


@dataclass(frozen=True)
class Fixture:
    version: str
    scenarios: list[Scenario]


@dataclass(frozen=True)
class Snapshot:
    entries: int
    pending_quotes: int
    memories: int


def normalize(text: str | None) -> str:
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower()


def contains_expected_phrase(reply: str, expected: str) -> bool:
    normalized = normalize(expected)
    if len(normalized) > 3:
        return normalized in reply
    pattern = r"(?<!\w)" + re.escape(normalized) + r"(?!\w)"
    return re.search(pattern, reply, flags=re.DOTALL) is not None


def redact(value: str | None) -> str:
    return f"<redacted:length={len(value) if value else 0}>"


def read_fixture(path: str) -> Fixture:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    scenarios = []
    for s in data.get("scenarios") or []:
        turns = [
            Turn(
                input=t["input"],
                assertions=[
                    Expectation(
                        category=a["category"],
                        type=a["type"],
                        critical=a.get("critical", False),
                        tool=a.get("tool"),
                        outcome=a.get("outcome"),
                        value=a.get("value"),
                        values=a.get("values"),
                    )
                    for a in t.get("assertions") or []
                ],
            )
            for t in s.get("turns") or []
        ]
        scenarios.append(Scenario(id=s["id"], turns=turns, start_onboarded=s.get("startOnboarded", False)))
    return Fixture(version=data.get("version", ""), scenarios=scenarios)


async def _clean_user_state(session: AsyncSession, terminal: TerminalSettings) -> None:
    user_id_str = str(terminal.user_id)
    await session.execute(
        delete(MessagingOutboundMessage).where(
            MessagingOutboundMessage.provider == "terminal",
            MessagingOutboundMessage.conversation_id == user_id_str,
        )
    )
    await session.execute(delete(MessagingInboxMessage).where(MessagingInboxMessage.provider == "terminal"))
    await session.execute(delete(FoodUser).where(FoodUser.telegram_user_id == terminal.user_id))
    await session.commit()


async def _snapshot(session: AsyncSession, terminal: TerminalSettings) -> Snapshot:
    user_id = (
        await session.execute(select(FoodUser.id).where(FoodUser.telegram_user_id == terminal.user_id))
    ).scalar_one_or_none()
    if user_id is None:
        return Snapshot(0, 0, 0)
    entries = (
        await session.execute(
            select(func.count())
            .select_from(FoodEntry)
            .where(FoodEntry.user_id == user_id, FoodEntry.deleted_at.is_(None))
        )
    ).scalar_one()
    quotes = (
        await session.execute(
            select(func.count()).select_from(PendingNutritionQuote).where(PendingNutritionQuote.user_id == user_id)
        )
    ).scalar_one()
    memories = (
        await session.execute(
            select(func.count()).select_from(ConversationMemory).where(ConversationMemory.user_id == user_id)
        )
    ).scalar_one()
    return Snapshot(entries, quotes, memories)


def _label(expectation: Expectation) -> str:
    suffix = f":{expectation.tool}" if expectation.tool else ""
    return f"{expectation.category}:{expectation.type}{suffix}"


def _evaluate(assertions: list[Expectation], reply: str, trace, state: Snapshot) -> list[eval_scorer.AssertionResult]:
    tools = trace.tools if trace is not None else []
    normalized_reply = normalize(reply)
    results = []
    for expectation in assertions:
        if expectation.type == "tool_required":
            passed = any(t.name == expectation.tool for t in tools)
        elif expectation.type == "tool_forbidden":
            passed = all(t.name != expectation.tool for t in tools)
        elif expectation.type == "tool_outcome":
            passed = any(t.name == expectation.tool and t.outcome == expectation.outcome for t in tools)
        elif expectation.type == "entries_exact":
            passed = state.entries == expectation.value
        elif expectation.type == "entries_at_least":
            passed = state.entries >= expectation.value
        elif expectation.type == "entries_at_most":
            passed = state.entries <= expectation.value
        elif expectation.type == "reply_contains_any":
            passed = bool(expectation.values) and any(
                contains_expected_phrase(normalized_reply, v) for v in expectation.values
            )
        elif expectation.type == "reply_not_contains":
            passed = not expectation.values or all(normalize(v) not in normalized_reply for v in expectation.values)
        else:
            raise ValueError(f"Unknown evaluation assertion: {expectation.type}")
        category = eval_scorer.Category[expectation.category]
        results.append(eval_scorer.AssertionResult(category, expectation.critical, passed, _label(expectation)))
    return results


@dataclass
class _OutcomeMetrics:
    scenario_runs: int = 0
    leaked_scenarios: int = 0
    first_turns: int = 0
    first_turn_captures: int = 0
    turns: int = 0
    entry_mutations: int = 0
    corrections: int = 0
    undos: int = 0
    clarifications: int = 0

    def record_scenario_start(self, before: Snapshot) -> None:
        self.scenario_runs += 1
        if before.entries != 0 or before.pending_quotes != 0 or before.memories != 0:
            self.leaked_scenarios += 1

    def record_turn(self, index: int, before: Snapshot, after: Snapshot, reply: str) -> None:
        self.turns += 1
        delta = after.entries - before.entries
        if index == 0:
            self.first_turns += 1
            if delta > 0:
                self.first_turn_captures += 1
        if delta > 0:
            self.entry_mutations += 1
        if delta < 0:
            self.corrections += 1
        normalized = normalize(reply)
        if "restored" in normalized or "restaurat" in normalized:
            self.undos += 1
        if any(kw in normalized for kw in ("how much", "quantity", "cantitate", "which one")):
            self.clarifications += 1

    def summary(self) -> dict[str, Any]:
        rate = 0.0 if self.first_turns == 0 else round((self.first_turn_captures / self.first_turns) * 1000) / 1000
        return {
            "scenarioRuns": self.scenario_runs,
            "firstTurnEntryRate": rate,
            "entryMutations": self.entry_mutations,
            "corrections": self.corrections,
            "undoRestorations": self.undos,
            "clarificationReplies": self.clarifications,
            "crossScenarioLeakage": self.leaked_scenarios,
            "turns": self.turns,
        }


def _baseline_delta(current: eval_scorer.Score, terminal: TerminalSettings) -> dict[str, Any]:
    if not terminal.eval_baseline_file:
        return {}
    try:
        prior = json.loads(Path(terminal.eval_baseline_file).read_text(encoding="utf-8"))
        old_score = prior["score"]
        delta: dict[str, Any] = {
            "qualityScore": round((current.quality_score - float(old_score["qualityScore"])) * 10) / 10
        }
        for name, value in current.categories.items():
            delta[name] = round((value - float(old_score["categories"][name])) * 10) / 10
        delta["baseline"] = terminal.eval_baseline_file
        return delta
    except Exception:  # noqa: BLE001 -- dev-only eval report tool, a bad baseline file must not crash the run
        return {"error": "baseline unreadable"}


def _report_path(terminal: TerminalSettings) -> Path:
    if terminal.report_file:
        return Path(terminal.report_file)
    return Path("eval-reports") / f"live-eval-{int(datetime.now(UTC).timestamp() * 1000)}.json"


def _print(score: eval_scorer.Score, output: Path) -> None:
    print(f"Live evaluation: {score.quality_score:.1f}/100 ({score.band}); safety release: {'PASS' if score.safety_release_passed else 'FAIL'}")
    print(f"Categories: {score.categories}")
    if score.critical_failures:
        print(f"Critical failures: {score.critical_failures}")
    print(f"Report: {output.resolve()}")


async def run(fixture_path: str, chat: TerminalConversation, settings: Settings, terminal: TerminalSettings) -> int:
    from app.db.base import session_scope

    fixture = read_fixture(fixture_path)
    scenarios = fixture.scenarios
    if terminal.eval_scenario:
        scenarios = [s for s in scenarios if s.id == terminal.eval_scenario]
    if not scenarios:
        raise ValueError("No evaluation scenarios selected")

    runs: list[dict[str, Any]] = []
    all_assertions: list[eval_scorer.AssertionResult] = []
    outcomes = _OutcomeMetrics()

    for scenario in scenarios:
        for repetition in range(1, terminal.eval_repeats + 1):
            async with session_scope() as session:
                await _clean_user_state(session, terminal)
                before = await _snapshot(session, terminal)
            outcomes.record_scenario_start(before)
            turns: list[dict[str, Any]] = []
            for turn_index, turn in enumerate(scenario.turns):
                response = await chat.send(turn.input)
                async with session_scope() as session:
                    after = await _snapshot(session, terminal)
                results = _evaluate(turn.assertions, response.reply, response.trace, after)
                run_label = f"{scenario.id}#{repetition}/"
                outcomes.record_turn(turn_index, before, after, response.reply)
                all_assertions.extend(
                    eval_scorer.AssertionResult(r.category, r.critical, r.passed, run_label + r.label) for r in results
                )
                turns.append(
                    {
                        "input": turn.input if terminal.eval_full_report else redact(turn.input),
                        "reply": response.reply if terminal.eval_full_report else redact(response.reply),
                        "trace": response.trace,
                        "before": before,
                        "after": after,
                        "assertions": results,
                    }
                )
                before = after
            runs.append(
                {"scenario": scenario.id, "startOnboarded": scenario.start_onboarded, "repetition": repetition, "turns": turns}
            )

    score = eval_scorer.score(all_assertions)
    output = _report_path(terminal)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "ranAt": datetime.now(UTC).isoformat(),
        "fixture": fixture_path,
        "fixtureVersion": fixture.version,
        "model": settings.openai_model,
        "repeats": terminal.eval_repeats,
        "fullText": terminal.eval_full_report,
        "score": score,
        "userOutcomes": outcomes.summary(),
        "runs": runs,
        "baselineDelta": _baseline_delta(score, terminal),
    }
    output.write_text(json.dumps(report, indent=2, default=_json_default), encoding="utf-8")
    _print(score, output)
    return 0 if score.safety_release_passed and score.quality_score >= 75 else 1


def _json_default(value: Any) -> Any:
    if isinstance(value, eval_scorer.Score):
        return {
            "qualityScore": value.quality_score,
            "safetyReleasePassed": value.safety_release_passed,
            "categories": value.categories,
            "criticalFailures": value.critical_failures,
            "band": value.band,
        }
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(value)
    if isinstance(value, eval_scorer.Category):
        return value.name
    return str(value)
