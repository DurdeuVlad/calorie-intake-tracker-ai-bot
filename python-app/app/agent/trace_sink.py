from typing import Protocol

from app.domain.agent_types import AgentContext, AgentReply, AgentToolResult, ToolCall


class AgentTraceSink(Protocol):
    def started(self, context: AgentContext) -> None: ...

    def model_reply(self, reply: AgentReply | None) -> None: ...

    def tool_result(self, call: ToolCall, result: AgentToolResult) -> None: ...

    def completed(self, reply: str) -> None: ...


class NoopTraceSink:
    def started(self, context: AgentContext) -> None:
        pass

    def model_reply(self, reply: AgentReply | None) -> None:
        pass

    def tool_result(self, call: ToolCall, result: AgentToolResult) -> None:
        pass

    def completed(self, reply: str) -> None:
        pass
