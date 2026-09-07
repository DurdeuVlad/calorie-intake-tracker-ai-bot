"""Feedback tool: lets the agent save user feedback and bug reports."""

from app.db.constraints import MAX_TEXT_CHARS
from app.domain.agent_types import AgentContext, AgentToolResult
from app.repositories import feedback_repo
from app.tools.shared import ValidationError, _text


async def save_feedback(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    """Save a user feedback or bug report. Called when the user says something
    unexpected happened or explicitly reports a problem."""
    kind = (args.get("kind") or "bug").strip().lower() if isinstance(args.get("kind"), str) else "bug"
    if kind not in ("bug", "correction", "suggestion"):
        kind = "bug"
    try:
        message = _text(args, "message", MAX_TEXT_CHARS * 4)
    except ValidationError:
        return AgentToolResult.failure("VALIDATION_ERROR", "A feedback message is required.")
    if not message or not message.strip():
        return AgentToolResult.failure("VALIDATION_ERROR", "A feedback message is required.")

    context_text = args.get("context") if isinstance(args.get("context"), str) else None
    if context_text and len(context_text) > MAX_TEXT_CHARS * 8:
        context_text = context_text[: MAX_TEXT_CHARS * 8]

    record = await feedback_repo.save(
        session, context.user, kind=kind, message=message.strip(), context=context_text
    )
    return AgentToolResult.success({"saved": True, "id": record.id, "kind": kind})


async def get_recent_feedback(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    """Read the caller's own recently submitted feedback. Call this when asked
    what feedback was logged or recorded; never call save_feedback again just
    to answer that question."""
    rows = await feedback_repo.recent(session, context.user)
    return AgentToolResult.success(
        {"feedback": [{"message": row.message, "loggedAt": row.created_at.isoformat()} for row in rows]}
    )
