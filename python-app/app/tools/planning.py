"""Planning tools: plan_todos and complete_todo."""


from app.db.constraints import MAX_TODO_CHARS, MAX_TODOS
from app.domain.agent_types import AgentToolResult
from app.tools.shared import ValidationError, _text, _validate_text


async def plan_todos(executor, session, context, args, todos: list[str]) -> AgentToolResult:
    raw = args.get("todos")
    if not isinstance(raw, list) or len(raw) > MAX_TODOS:
        return AgentToolResult.failure("VALIDATION_ERROR", "Provide up to six short todo steps.")
    validated: list[str] = []
    try:
        for value in raw:
            if not isinstance(value, str):
                raise ValidationError("Each todo step must be text.")
            value = _validate_text(value, "todo", MAX_TODO_CHARS).strip()
            if value:
                validated.append(value)
    except ValidationError as failure:
        return AgentToolResult.failure("VALIDATION_ERROR", str(failure))
    todos.clear()
    todos.extend(validated)
    return AgentToolResult.success({"todos": list(todos)})


async def complete_todo(executor, session, context, args, todos: list[str]) -> AgentToolResult:
    todo = _text(args, "todo", MAX_TODO_CHARS)
    if todo is None or todo not in todos:
        return AgentToolResult.failure("NOT_FOUND", "That todo is not in the current run.")
    todos.remove(todo)
    return AgentToolResult.success({"todos": list(todos)})
