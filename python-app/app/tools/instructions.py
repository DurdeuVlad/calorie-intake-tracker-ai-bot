"""Progressive disclosure tool: load_instructions."""

from app.agent.capabilities import registry as capabilities_registry
from app.domain.agent_types import AgentToolResult
from app.tools.shared import _str


async def load_instructions(executor, session, context, args, todos) -> AgentToolResult:
    topic = _str(args, "topic")
    if not topic:
        return AgentToolResult.failure("VALIDATION_ERROR", "A topic is required.")
    content = capabilities_registry.load(topic)
    if content is None:
        return AgentToolResult.failure("VALIDATION_ERROR", f"Unknown topic. Valid topics: {', '.join(capabilities_registry.valid_topics())}")
    return AgentToolResult.success({"topic": topic, "instructions": content})
