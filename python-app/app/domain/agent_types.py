from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.db.models.users import FoodUser


@dataclass(frozen=True)
class AgentContext:
    user: FoodUser
    chat_id: str
    romanian: bool
    message: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class AgentToolResult:
    ok: bool
    code: str
    data: dict[str, Any]
    user_hint: str | None

    @staticmethod
    def success(data: dict[str, Any]) -> "AgentToolResult":
        return AgentToolResult(True, "OK", data, None)

    @staticmethod
    def failure(code: str, hint: str) -> "AgentToolResult":
        return AgentToolResult(False, code, {}, hint)

    def to_json_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "code": self.code, "data": self.data, "userHint": self.user_hint}


class AgentToolFailure(Exception):
    """Raised by a tool handler to short-circuit with a specific AgentToolResult,
    distinct from an unexpected exception (which the caller maps to a generic
    TEMPORARY_FAILURE)."""

    def __init__(self, result: AgentToolResult) -> None:
        super().__init__(result.user_hint or result.code)
        self.result = result


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class AgentExchange:
    call: ToolCall
    result: AgentToolResult


@dataclass(frozen=True)
class AgentReply:
    text: str | None
    tool_calls: list[ToolCall]
