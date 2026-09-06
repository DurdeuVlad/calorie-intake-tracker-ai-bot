"""Food alias tools: save_alias and resolve_alias (issue #108).

Aliases are user-scoped shorthand mappings. save_alias creates or updates an
alias. resolve_alias looks up an alias and returns the canonical name plus any
nutrition shortcut. Both enforce ownership: a user can only save and resolve
their own aliases."""

import re
from typing import Any

from app.domain.agent_types import AgentContext, AgentToolResult
from app.repositories import food_alias_repo
from app.tools.shared import ValidationError

# Reject control characters (including newlines, tabs, and other non-printable
# bytes) in alias and canonical name strings. This prevents stored-data
# prompt injection via control characters and keeps receipts clean.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")

_MAX_ALIAS_LENGTH = 255
_MAX_CANONICAL_LENGTH = 255


def _is_int(value: Any) -> bool:
    """True only for genuine integers, not booleans (Python's bool is a subclass of int)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _clean_text(value: str, field_name: str, max_length: int) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValidationError(f"{field_name} is required.")
    if len(stripped) > max_length:
        raise ValidationError(f"{field_name} must be at most {max_length} characters.")
    if _CONTROL_CHAR_RE.search(stripped):
        raise ValidationError(f"{field_name} must not contain control characters.")
    return stripped


def _alias_summary(alias) -> dict[str, Any]:
    result: dict[str, Any] = {
        "alias": alias.alias,
        "canonicalName": alias.canonical_name,
    }
    if alias.calories_per_100g is not None:
        result["caloriesPer100g"] = alias.calories_per_100g
    if alias.fixed_calories is not None:
        result["fixedCalories"] = alias.fixed_calories
    return result


async def save_alias(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    raw_alias = args.get("alias")
    raw_canonical = args.get("canonicalName")
    if not isinstance(raw_alias, str) or not isinstance(raw_canonical, str):
        raise ValidationError("alias and canonicalName must be text.")
    alias = _clean_text(raw_alias, "alias", _MAX_ALIAS_LENGTH)
    canonical = _clean_text(raw_canonical, "canonicalName", _MAX_CANONICAL_LENGTH)

    calories_per_100g = args.get("caloriesPer100g")
    fixed_calories = args.get("fixedCalories")
    if calories_per_100g is not None and (not _is_int(calories_per_100g) or calories_per_100g <= 0 or calories_per_100g > 10000):
        raise ValidationError("caloriesPer100g must be between 1 and 10000.")
    if fixed_calories is not None and (not _is_int(fixed_calories) or fixed_calories < 0 or fixed_calories > 10000):
        raise ValidationError("fixedCalories must be between 0 and 10000.")
    if calories_per_100g is not None and fixed_calories is not None:
        raise ValidationError("Provide either caloriesPer100g or fixedCalories, not both.")

    record = await food_alias_repo.upsert(
        session,
        context.user,
        alias,
        canonical,
        calories_per_100g=calories_per_100g,
        fixed_calories=fixed_calories,
    )
    return AgentToolResult.success({
        "ok": True,
        "alias": _alias_summary(record),
        "message": f"Saved alias '{record.alias}' → '{record.canonical_name}'.",
    })


async def resolve_alias(executor, session, context: AgentContext, args, todos) -> AgentToolResult:
    raw_alias = args.get("alias")
    if not isinstance(raw_alias, str):
        raise ValidationError("alias must be text.")
    alias = _clean_text(raw_alias, "alias", _MAX_ALIAS_LENGTH)
    record = await food_alias_repo.find_by_user_and_alias_ignore_case(session, context.user, alias)
    if record is None:
        return AgentToolResult.success({"resolved": False, "alias": alias})
    return AgentToolResult.success({"resolved": True, "alias": _alias_summary(record)})
