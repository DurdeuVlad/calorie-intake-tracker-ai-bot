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

_VALID_TARGET_MODES = {"max", "min"}
_VALID_BOOL_KEYS = {
    "reportsEnabled",
    "dayBoundaryReminderEnabled",
    "budgetAlertsEnabled",
    "trackingNudgeEnabled",
    "skipCalorieTarget",
}


async def get_settings(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    s = await executor._settings_for(session, context)
    return AgentToolResult.success({
        "name": context.user.display_name or "",
        "timezone": s.timezone,
        "calorieTarget": "unset" if s.calorie_target is None else s.calorie_target,
        "reportsEnabled": s.reports_enabled,
        "dayBoundaryHour": s.day_boundary_hour,
        "dayBoundaryReminderEnabled": s.day_boundary_reminder_enabled,
        "targetMode": s.target_mode,
        "budgetAlertsEnabled": s.budget_alerts_enabled,
        "trackingNudgeEnabled": s.tracking_nudge_enabled,
    })


async def update_settings(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    s = await executor._settings_for(session, context)
    _known_keys = ("name", "timezone", "calorieTarget", "reportsEnabled", "skipCalorieTarget",
                   "dayBoundaryHour", "dayBoundaryReminderEnabled", "targetMode",
                   "budgetAlertsEnabled", "trackingNudgeEnabled")
    if not args or all(args.get(key) is None for key in _known_keys):
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

    day_boundary_hour = None
    if "dayBoundaryHour" in args and args["dayBoundaryHour"] is not None:
        try:
            day_boundary_hour = _optional_int(args, "dayBoundaryHour", min_value=0, max_value=23)
        except ValidationError:
            return AgentToolResult.failure("VALIDATION_ERROR", "dayBoundaryHour must be 0-23.")
        if day_boundary_hour is None:
            return AgentToolResult.failure("VALIDATION_ERROR", "dayBoundaryHour must be 0-23.")

    target_mode = None
    if "targetMode" in args and args["targetMode"] is not None:
        target_mode = args["targetMode"]
        if target_mode not in _VALID_TARGET_MODES:
            return AgentToolResult.failure("VALIDATION_ERROR", "targetMode must be 'max' or 'min'.")

    bool_fields: dict[str, bool] = {}
    for key in _VALID_BOOL_KEYS:
        if key in args and args[key] is not None:
            val = args[key]
            if not isinstance(val, bool):
                return AgentToolResult.failure("VALIDATION_ERROR", f"{key} must be true or false.")
            bool_fields[key] = val

    if name is not None:
        context.user.display_name = name
        if not s.onboarding_completed and s.onboarding_stage == "NAME":
            s.require_timezone()
    if timezone is not None:
        s.timezone = timezone
        if not s.onboarding_completed and s.onboarding_stage == "TIMEZONE":
            s.require_calorie_target()
    if target is not None:
        s.calorie_target = target
        if not s.onboarding_completed and s.onboarding_stage == "CALORIE_TARGET":
            s.skip_calorie_target()
    if bool_fields.get("skipCalorieTarget") and not s.onboarding_completed and s.onboarding_stage == "CALORIE_TARGET":
        s.skip_calorie_target()
    if day_boundary_hour is not None:
        s.day_boundary_hour = day_boundary_hour
    if target_mode is not None:
        s.target_mode = target_mode
    if "reportsEnabled" in bool_fields:
        s.reports_enabled = bool_fields["reportsEnabled"]
    if "dayBoundaryReminderEnabled" in bool_fields:
        s.day_boundary_reminder_enabled = bool_fields["dayBoundaryReminderEnabled"]
    if "budgetAlertsEnabled" in bool_fields:
        s.budget_alerts_enabled = bool_fields["budgetAlertsEnabled"]
    if "trackingNudgeEnabled" in bool_fields:
        s.tracking_nudge_enabled = bool_fields["trackingNudgeEnabled"]
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
