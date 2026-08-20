"""In-memory trace for local prompt evaluation; stores tool names and outcomes
only. Terminal usage is single-threaded and sequential, so a simple "current
run" attribute (no thread-local/contextvar) is sufficient, unlike the Java
predecessor which needed a ThreadLocal for its servlet-container threading
model."""

from dataclasses import dataclass, field

from app.domain.agent_types import AgentContext, AgentReply, AgentToolResult, ToolCall


@dataclass
class ToolTrace:
    name: str
    outcome: str


@dataclass
class Trace:
    tools: list[ToolTrace]
    model_turns: int
    reply_length: int


@dataclass
class _MutableTrace:
    tools: list[ToolTrace] = field(default_factory=list)
    model_turns: int = 0


class TerminalTraceCollector:
    def __init__(self) -> None:
        self._active: _MutableTrace | None = None
        self._completed: list[Trace] = []

    def started(self, context: AgentContext) -> None:
        self._active = _MutableTrace()

    def model_reply(self, reply: AgentReply | None) -> None:
        if self._active is not None:
            self._active.model_turns += 1

    def tool_result(self, call: ToolCall, result: AgentToolResult) -> None:
        if self._active is not None:
            self._active.tools.append(ToolTrace(call.name, result.code))

    def completed(self, reply: str) -> None:
        if self._active is not None:
            self._completed.append(Trace(list(self._active.tools), self._active.model_turns, len(reply or "")))
            self._active = None

    def await_trace(self) -> Trace | None:
        return self._completed.pop(0) if self._completed else None
