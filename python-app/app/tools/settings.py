"""Settings tools: get_settings, update_settings, save_private_food."""

from datetime import UTC, datetime

from app.db.models.nutrition import PrivateFood
from app.domain.agent_types import AgentContext, AgentToolResult
from app.repositories import private_food_repo
from app.tools.shared import _str


async def get_settings(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    s = await executor._settings_for(session, context)
    return AgentToolResult.success({"timezone": s.timezone, "calorieTarget": "unset" if s.calorie_target is None else s.calorie_target, "reportsEnabled": s.reports_enabled})


async def update_settings(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    s = await executor._settings_for(session, context)
    if "timezone" in args:
        tz = _str(args, "timezone")
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            return AgentToolResult.failure("VALIDATION_ERROR", "Use a valid IANA timezone.")
        s.timezone = tz
    if "calorieTarget" in args and args["calorieTarget"] is not None:
        target = int(args["calorieTarget"])
        if target < 1200 or target > 5000:
            return AgentToolResult.failure("VALIDATION_ERROR", "The calorie target must be 1200-5000.")
        s.calorie_target = target
    if "reportsEnabled" in args and args["reportsEnabled"] is not None:
        value = str(args["reportsEnabled"]).lower()
        if value not in ("true", "false"):
            return AgentToolResult.failure("VALIDATION_ERROR", "reportsEnabled must be true or false.")
        s.reports_enabled = value == "true"
    return await get_settings(executor, session, context, args, todos)


async def save_private_food(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    name = _str(args, "name")
    kcal = int(args["caloriesPer100g"]) if args.get("caloriesPer100g") is not None else None
    if not name or kcal is None or kcal < 0 or kcal > 10000:
        return AgentToolResult.failure("VALIDATION_ERROR", "A food name and valid calories per 100 g are required.")
    existing = await private_food_repo.find_by_user_and_name_ignore_case(session, context.user, name)
    if existing is None:
        session.add(PrivateFood(user_id=context.user.id, name=name, calories_per_100g=kcal, created_at=datetime.now(UTC)))
    else:
        existing.calories_per_100g = kcal
    return AgentToolResult.success({"name": name, "caloriesPer100g": kcal})
