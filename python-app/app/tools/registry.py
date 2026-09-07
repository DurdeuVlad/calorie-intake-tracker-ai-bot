"""Tool dispatch registry mapping tool names to handler functions.

Each handler is an async function taking (executor, session, context, args, todos)
and returning AgentToolResult. The executor instance provides shared state
(off client, searxng, browserless, refresh_daily_status, web search cache)."""

from collections.abc import Awaitable, Callable

from app.tools import (
    aliases,
    feedback,
    instructions,
    journal_actions,
    nutrition,
    planning,
    settings,
)

Handler = Callable[..., Awaitable]

HANDLERS: dict[str, Handler] = {
    # always_available
    "get_today_summary": journal_actions.get_today_summary,
    "get_weekly_summary": journal_actions.get_weekly_summary,
    "search_entries": journal_actions.search_entries,
    "search_food_history": journal_actions.search_food_history,
    "get_entry": journal_actions.get_entry,
    "apply_journal_actions": journal_actions.apply_journal_actions,
    "undo_last_change": journal_actions.undo_last_change,
    "load_instructions": instructions.load_instructions,
    # nutrition
    "resolve_nutrition": nutrition.resolve_nutrition,
    "lookup_food": nutrition.resolve_nutrition,
    "get_private_food": nutrition.get_private_food,
    "search_packaged_food": nutrition.search_packaged_food,
    "get_pending_nutrition_quotes": nutrition.get_pending_nutrition_quotes,
    "select_packaged_food": nutrition.select_packaged_food,
    "search_web": nutrition.search_web,
    "fetch_web_page": nutrition.fetch_web_page,
    "estimate_food": nutrition.estimate_food,
    "save_private_food": settings.save_private_food,
    # aliases
    "save_alias": aliases.save_alias,
    "resolve_alias": aliases.resolve_alias,
    # settings
    "get_settings": settings.get_settings,
    "update_settings": settings.update_settings,
    # planning
    "plan_todos": planning.plan_todos,
    "complete_todo": planning.complete_todo,
    # feedback
    "save_feedback": feedback.save_feedback,
    "get_recent_feedback": feedback.get_recent_feedback,
}
