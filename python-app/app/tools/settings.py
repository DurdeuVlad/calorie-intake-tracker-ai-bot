"""Settings tools: get_settings, update_settings, save_private_food."""

from datetime import UTC, datetime

from app.db.constraints import (
    MAX_CALORIE_TARGET,
    MAX_CALORIES,
    MAX_TEXT_CHARS,
    MAX_TIMEZONE_CHARS,
    MIN_CALORIE_TARGET,
    MIN_CALORIES,
)
from app.db.models.nutrition import PrivateFood
from app.domain.agent_types import AgentContext, AgentToolResult
from app.repositories import private_food_repo
from app.tools.shared import ValidationError, _optional_int, _text


async def get_settings(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    s = await executor._settings_for(session, context)
    return AgentToolResult.success({"name": context.user.display_name or "", "timezone": s.timezone, "calorieTarget": "unset" if s.calorie_target is None else s.calorie_target, "reportsEnabled": s.reports_enabled})


async def update_settings(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    s = await executor._settings_for(session, context)
    if not args or all(args.get(key) is None for key in ("name", "timezone", "calorieTarget", "reportsEnabled")):
        return AgentToolResult.failure("VALIDATION_ERROR", "Provide at least one setting to update.")
    name = None
    if "name" in args and args["name"] is not None:
        try:
            name = _text(args, "name", MAX_TEXT_CHARS)
        except ValidationError:
            return AgentToolResult.failure("VALIDATION_ERROR", "Name must be 1-100 characters.")
        if not name or not name.strip():
            return AgentToolResult.failure("VALIDATION_ERROR", "Name must be 1-100 characters.")
        name = name.strip()

    timezone = None
    if "timezone" in args:
        timezone = _text(args, "timezone", MAX_TIMEZONE_CHARS)
        if not timezone or not timezone.strip():
            return AgentToolResult.failure("VALIDATION_ERROR", "Use a valid IANA timezone.")
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            return AgentToolResult.failure("VALIDATION_ERROR", "Use a valid IANA timezone.")

    target = None
    if "calorieTarget" in args and args["calorieTarget"] is not None:
        try:
            target = _optional_int(args, "calorieTarget", min_value=MIN_CALORIE_TARGET, max_value=MAX_CALORIE_TARGET)
        except ValidationError:
            return AgentToolResult.failure("VALIDATION_ERROR", "The calorie target must be an integer from 1200 to 5000.")
        if target is None:
            return AgentToolResult.failure("VALIDATION_ERROR", "The calorie target must be 1200-5000.")

    reports_enabled = None
    if "reportsEnabled" in args and args["reportsEnabled"] is not None:
        reports_enabled = args["reportsEnabled"]
        if not isinstance(reports_enabled, bool):
            return AgentToolResult.failure("VALIDATION_ERROR", "reportsEnabled must be true or false.")

    if name is not None:
        context.user.display_name = name
    if timezone is not None:
        s.timezone = timezone
    if target is not None:
        s.calorie_target = target
    if reports_enabled is not None:
        s.reports_enabled = reports_enabled
    current = await get_settings(executor, session, context, args, todos)
    return AgentToolResult.success({**current.data, "updated": True})


async def save_private_food(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    name = _text(args, "name", MAX_TEXT_CHARS)
    kcal = _optional_int(args, "caloriesPer100g", min_value=MIN_CALORIES, max_value=MAX_CALORIES)
    if not name or not name.strip() or kcal is None:
        return AgentToolResult.failure("VALIDATION_ERROR", "A food name and valid calories per 100 g are required.")
    existing = await private_food_repo.find_by_user_and_name_ignore_case(session, context.user, name)
    if existing is None:
        session.add(PrivateFood(user_id=context.user.id, name=name, calories_per_100g=kcal, created_at=datetime.now(UTC)))
    else:
        existing.calories_per_100g = kcal
    return AgentToolResult.success({"name": name, "caloriesPer100g": kcal})
