"""Planning tools: plan_todos and complete_todo."""


from app.domain.agent_types import AgentToolResult
from app.tools.shared import _str


async def plan_todos(executor, session, context, args, todos: list[str]) -> AgentToolResult:
    raw = args.get("todos")
    if not isinstance(raw, list):
        return AgentToolResult.failure("VALIDATION_ERROR", "Provide a short todo list.")
    todos.clear()
    for value in raw:
        if value is not None and str(value).strip() and len(todos) < 6:
            todos.append(str(value))
    return AgentToolResult.success({"todos": list(todos)})


async def complete_todo(executor, session, context, args, todos: list[str]) -> AgentToolResult:
    todo = _str(args, "todo")
    if todo is None or todo not in todos:
        return AgentToolResult.failure("NOT_FOUND", "That todo is not in the current run.")
    todos.remove(todo)
    return AgentToolResult.success({"todos": list(todos)})
