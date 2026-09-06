"""Journal mutation tools: apply_journal_actions (CREATE/EDIT/MOVE/DELETE) and undo_last_change."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.db.models.entries import FoodEntry, FoodItem
from app.db.models.journal_changes import JournalChangeSet
from app.db.models.nutrition import PendingNutritionQuote
from app.domain import journal_entry_snapshot as snapshot
from app.domain.agent_types import AgentToolFailure, AgentToolResult
from app.domain.quantity_unit import QuantityUnit
from app.repositories import (
    food_entry_repo,
    food_item_repo,
    journal_change_set_repo,
    pending_nutrition_quote_repo,
)
from app.tools.shared import (
    MAX_ACTIONS_PER_BATCH,
    ValidationError,
    _decimal_number,
    _normalize,
    _quantity_unit,
    _quote_id,
    _resolve_meal_instant,
    _search_date,
    _str,
    _summary,
    _unverified_source_claim,
)


async def _settings_for(executor, session, context):
    return await executor._settings_for(session, context)


async def _owned_entry(session, context, args) -> FoodEntry:
    if "entryId" not in args:
        raise ValidationError("An entry ID is required.")
    entry = await food_entry_repo.find_by_id_and_user(session, int(args["entryId"]), context.user)
    if entry is None:
        raise AgentToolFailure(AgentToolResult.failure("NOT_FOUND", "No matching journal entry exists."))
    return entry


def _action_success(
    action_type: str, entry: FoodEntry, timezone_name: str, receipt: dict[str, Any] | None = None,
    undo_deadline: datetime | None = None, derivation: str | None = None,
    source_url: str | None = None, source_name: str | None = None,
) -> dict[str, Any]:
    from zoneinfo import ZoneInfo

    local_date = entry.eaten_at.astimezone(ZoneInfo(timezone_name)).date()
    result: dict[str, Any] = {
        "ok": True,
        "type": action_type,
        "entry": _summary(entry),
        "date": local_date.isoformat(),
        "calories": entry.calories,
        "description": entry.original_message,
        "nutritionSource": entry.nutrition_source,
        "nutritionConfidence": entry.confidence,
    }
    if receipt:
        result["receipt"] = receipt
    if derivation:
        result["derivation"] = derivation
    if undo_deadline:
        result["undoDeadline"] = undo_deadline.isoformat()
    if source_url:
        result["sourceUrl"] = source_url
    if source_name:
        result["sourceName"] = source_name
    return result


def _action_failure(action_type: str, message: str) -> dict[str, Any]:
    return {"ok": False, "type": action_type, "message": message}


async def _create_action(executor, session, context, args, change_set, now, timezone_name) -> dict[str, Any]:
    description = _str(args, "description") or _str(args, "name")
    if not description:
        raise ValidationError("A description is required.")
    calories: int | None = int(args["calories"]) if "calories" in args and args["calories"] is not None else None
    requested_source = _str(args, "nutritionSource")
    source = _normalize(requested_source, "manual", {"manual", "private", "open_food_facts", "open_food_facts_estimate", "ai_estimate", "mixed"})
    confidence = _normalize(_str(args, "nutritionConfidence"), "high" if source == "manual" else "estimate", {"high", "estimate", "unknown"})
    quantity = _decimal_number(args, "quantity")
    unit = _quantity_unit(_str(args, "unit"), quantity)
    consumed: list[PendingNutritionQuote] = []
    receipt: dict[str, Any] = {"quantity": quantity, "unit": unit}
    unverified_source = args.get("quoteId") is None and _unverified_source_claim(requested_source)
    derivation: str | None = None
    source_url: str | None = None
    source_name: str | None = None

    if args.get("quoteId") is None and source in {"open_food_facts", "open_food_facts_estimate"}:
        raise ValidationError("Open Food Facts provenance requires a server-issued quoteId.")

    if unverified_source:
        source = "manual"
        confidence = "unknown"

    if args.get("quoteId") is not None:
        quote_id = _quote_id(args)
        quote = await pending_nutrition_quote_repo.lock_owned_active(session, quote_id, context.user, datetime.now(UTC)) if quote_id else None
        if quote is None:
            raise AgentToolFailure(AgentToolResult.failure("NOT_FOUND", "The selected nutrition result is unavailable or expired."))
        quoted = executor._quote_item(quote)
        calories = quoted.total_calories
        quantity = quoted.grams
        unit = QuantityUnit.G.value
        receipt.update({"quantity": quantity, "unit": unit})
        description = description or quoted.name
        source = "open_food_facts" if quote.quote_type == "PACKAGED_MATCH" else "ai_estimate"
        confidence = "high" if quote.quote_type == "PACKAGED_MATCH" else "estimate"
        if quote.quote_type == "AI_ESTIMATE":
            receipt.update({"caloriesPer100g": quote.calories_per_100g, "basis": quote.estimate_basis or "AI estimate"})
            derivation = f"{quantity} g × {quote.calories_per_100g} kcal/100 g = {calories} kcal"
        else:
            derivation = f"round({quantity} g × {quote.calories_per_100g} kcal / 100 g) = {calories} kcal"
            source_url = quote.source_url
            source_name = "Open Food Facts"
        consumed.append(quote)

    if calories is None or calories <= 0 or calories > 10000:
        raise ValidationError("Calories must be between 1 and 10000.")
    if quantity is not None and (quantity <= 0 or quantity > 100000):
        raise ValidationError("Quantity must be positive.")

    eaten_at = _resolve_meal_instant(context, timezone_name, _str(args, "date"), _str(args, "localTime"))
    entry = FoodEntry(user_id=context.user.id, original_message=description, eaten_at=eaten_at, calories=calories, nutrition_source=source, confidence=confidence, created_at=now)
    session.add(entry)
    await session.flush()
    item = FoodItem(
        entry_id=entry.id, name=description, quantity=Decimal(str(quantity)) if quantity is not None else None,
        quantity_unit=unit, calories=calories, nutrition_source=source, nutrition_confidence=confidence,
    )
    session.add(item)
    await session.flush()

    for quote in consumed:
        if quote.quote_type == "PACKAGED_MATCH":
            await executor._cache_selected(session, quote)
            executor._record_packaged_evidence(session, entry, item, quote, now)
        await session.delete(quote)

    after = snapshot.capture(entry, [item])
    if change_set is not None:
        change_set.add_mutation("CREATE", None, after)
    if unverified_source:
        receipt["basis"] = "unverified source label ignored; calories supplied in the message"
    elif source == "manual":
        receipt["basis"] = "user-provided calories"
    if derivation is None and receipt.get("caloriesPer100g") is not None and quantity is not None and unit == "g":
        per_100g = receipt["caloriesPer100g"]
        derivation = f"{quantity} g × {per_100g} kcal/100 g = {calories} kcal"
    undo_deadline = now + timedelta(minutes=10) if change_set is not None else None
    return _action_success(
        "CREATE", entry, timezone_name, receipt,
        undo_deadline=undo_deadline, derivation=derivation,
        source_url=source_url, source_name=source_name,
    )


async def _edit_action(executor, session, context, args, change_set, timezone_name) -> dict[str, Any]:
    entry = await _owned_entry(session, context, args)
    current = await food_item_repo.find_by_entry(session, entry)
    before = snapshot.capture(entry, current)
    description = _str(args, "description") or entry.original_message
    calories = int(args["calories"]) if "calories" in args and args["calories"] is not None else entry.calories
    if calories is None or calories < 0 or calories > 10000:
        raise ValidationError("Calories must be between 0 and 10000.")
    entry.revise(description, calories)
    executor._synchronize_items_after_edit(current, description, calories)
    after = snapshot.capture(entry, current)
    if change_set is not None:
        change_set.add_mutation("EDIT", before, after)
    undo_deadline = context.started_at + timedelta(minutes=10) if change_set is not None else None
    return _action_success("EDIT", entry, timezone_name, undo_deadline=undo_deadline)


async def _move_action(executor, session, context, args, change_set, timezone_name) -> dict[str, Any]:
    entry = await _owned_entry(session, context, args)
    current = await food_item_repo.find_by_entry(session, entry)
    before = snapshot.capture(entry, current)
    new_when = _resolve_meal_instant(context, timezone_name, _str(args, "date"), _str(args, "localTime"), entry.eaten_at)
    entry.move_to(new_when, context.started_at)
    after = snapshot.capture(entry, current)
    if change_set is not None:
        change_set.add_mutation("MOVE", before, after)
    undo_deadline = context.started_at + timedelta(minutes=10) if change_set is not None else None
    return _action_success("MOVE", entry, timezone_name, undo_deadline=undo_deadline)


async def _delete_action(executor, session, context, args, change_set, now, timezone_name) -> dict[str, Any]:
    entry = await _owned_entry(session, context, args)
    current = await food_item_repo.find_by_entry(session, entry)
    before = snapshot.capture(entry, current)
    entry.mark_deleted(now)
    after = snapshot.capture(entry, current)
    if change_set is not None:
        change_set.add_mutation("DELETE", before, after)
    undo_deadline = now + timedelta(minutes=10) if change_set is not None else None
    return _action_success("DELETE", entry, timezone_name, undo_deadline=undo_deadline)


async def apply_journal_actions(executor, session, context, args, todos) -> AgentToolResult:
    requested = args.get("actions")
    if not isinstance(requested, list) or not requested:
        return AgentToolResult.failure("VALIDATION_ERROR", "At least one journal action is required.")
    if len(requested) > MAX_ACTIONS_PER_BATCH:
        return AgentToolResult.failure("VALIDATION_ERROR", "A message may contain at most 20 journal actions.")

    settings = await executor._settings_for(session, context)
    now = context.started_at
    await journal_change_set_repo.delete_expired(session, now)
    change_set = JournalChangeSet(user_id=context.user.id, created_at=now, expires_at=now + timedelta(minutes=10))

    results: list[dict[str, Any]] = []
    changed = 0
    for raw in requested:
        if not isinstance(raw, dict):
            results.append(_action_failure("ACTION", "Invalid journal action."))
            continue
        action_type = (raw.get("type") or "ACTION").upper()
        try:
            if action_type == "CREATE":
                result = await _create_action(executor, session, context, raw, change_set, now, settings.timezone)
            elif action_type == "EDIT":
                result = await _edit_action(executor, session, context, raw, change_set, settings.timezone)
            elif action_type == "MOVE":
                result = await _move_action(executor, session, context, raw, change_set, settings.timezone)
            elif action_type == "DELETE":
                result = await _delete_action(executor, session, context, raw, change_set, now, settings.timezone)
            else:
                result = _action_failure(action_type, "Unsupported journal action.")
            if result.get("ok"):
                await session.flush()
                changed += 1
            results.append(result)
        except AgentToolFailure as failure:
            results.append(_action_failure(action_type, failure.result.user_hint or "The action was rejected."))
        except ValidationError as failure:
            results.append(_action_failure(action_type, str(failure) or "The action details are invalid."))

    if changed > 0:
        session.add(change_set)
        await session.flush()
        await executor.refresh_daily_status(session, context.user, context.chat_id)

    return AgentToolResult.success(
        {"results": results, "successful": changed, "failed": len(results) - changed, "undoAvailable": changed > 0}
    )


async def undo_last_change(executor, session, context, args, todos) -> AgentToolResult:
    now = context.started_at
    change_set = await journal_change_set_repo.find_first_undoable(session, context.user, now)
    if change_set is None:
        return AgentToolResult.failure("NOT_FOUND", "There is no recent journal change to undo.")
    mutations = list(reversed(change_set.mutations))
    undone_actions: list[dict[str, Any]] = []
    for mutation in mutations:
        before = mutation.before_state
        after = mutation.after_state
        entry_id = before["entryId"] if before else after["entryId"]
        entry = await food_entry_repo.find_by_id_and_user(session, entry_id, context.user, include_deleted=True)
        if entry is None:
            continue
        if mutation.action_type == "CREATE":
            entry.mark_deleted(now)
            undone_actions.append({
                "type": "CREATE",
                "description": after["originalMessage"] if after else "entry",
                "calories": after["calories"] if after else None,
            })
            continue
        executor._restore_from(entry, before)
        await food_item_repo.delete_by_entry(session, entry)
        await session.flush()
        for item_snapshot in before.get("items", []):
            session.add(snapshot.recreate_item_for(entry, item_snapshot))
        undone_actions.append({
            "type": mutation.action_type,
            "description": before["originalMessage"] if before else "entry",
            "calories": before["calories"] if before else None,
        })
    change_set.mark_undone(now)
    await executor.refresh_daily_status(session, context.user, context.chat_id)
    return AgentToolResult.success({
        "changeSetId": change_set.id,
        "actions": len(mutations),
        "undoneActions": undone_actions,
    })


# --- read tools (search, get_entry, get_today_summary, get_weekly_summary) ---

async def get_today_summary(executor, session, context, args, todos) -> AgentToolResult:
    rows = await executor._for_today(session, context)
    total = sum(r.calories or 0 for r in rows)
    settings = await executor._settings_for(session, context)
    target = settings.calorie_target
    return AgentToolResult.success({"calories": total, "entries": len(rows), "target": "unset" if target is None else target})


async def get_weekly_summary(executor, session, context, args, todos) -> AgentToolResult:
    """Aggregate calories for the seven days ending on the requested reference date
    (default: today). Returns per-day totals plus a weekly total, daily average,
    and the caller's calorie target. Only owned, non-deleted entries are counted.
    The reference date is resolved with the same words/ISO rules as search_entries
    and must not be in the future."""
    from zoneinfo import ZoneInfo

    settings = await executor._settings_for(session, context)
    zone = ZoneInfo(settings.timezone)
    today = context.started_at.astimezone(zone).date()
    reference = _search_date(context, _str(args, "date"), today)
    if reference > today:
        return AgentToolResult.failure("VALIDATION_ERROR", "The reference date cannot be in the future.")

    end_date = reference
    start_date = end_date - timedelta(days=6)
    start, _ = food_entry_repo.day_bounds(start_date, zone)
    _, end = food_entry_repo.day_bounds(end_date, zone)
    rows = await food_entry_repo.find_between(session, context.user, start, end)

    per_day: dict[str, dict[str, Any]] = {}
    for offset in range(7):
        day = start_date + timedelta(days=offset)
        per_day[day.isoformat()] = {"date": day.isoformat(), "calories": 0, "entries": 0}

    for row in rows:
        day_key = row.eaten_at.astimezone(zone).date().isoformat()
        bucket = per_day.get(day_key)
        if bucket is None:
            continue
        bucket["calories"] += row.calories or 0
        bucket["entries"] += 1

    days = list(per_day.values())
    weekly_total = sum(d["calories"] for d in days)
    target = settings.calorie_target
    return AgentToolResult.success({
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "days": days,
        "weeklyCalories": weekly_total,
        "dailyAverage": round(weekly_total / 7) if weekly_total else 0,
        "target": "unset" if target is None else target,
    })


async def search_entries(executor, session, context, args, todos) -> AgentToolResult:
    from zoneinfo import ZoneInfo

    settings = await executor._settings_for(session, context)
    q = _str(args, "query")
    date_arg = _str(args, "date")
    from_arg = _str(args, "fromDate")
    to_arg = _str(args, "toDate")
    zone = ZoneInfo(settings.timezone)
    today = context.started_at.astimezone(zone).date()

    rows = await executor._search_entries_impl(session, context, q, date_arg, from_arg, to_arg, zone, today)
    return AgentToolResult.success({"entries": [_summary(r) for r in rows[:10]]})


async def get_entry(executor, session, context, args, todos) -> AgentToolResult:
    from app.tools.shared import _int_required

    entry = await food_entry_repo.find_by_id_and_user(session, _int_required(args, "entryId"), context.user)
    if entry is None:
        return AgentToolResult.failure("NOT_FOUND", "No matching journal entry exists.")
    return AgentToolResult.success({"entry": _summary(entry)})


async def search_food_history(executor, session, context, args, todos) -> AgentToolResult:
    """Search the caller's full journal history for a food term and return
    aggregated info: total count, first/last eaten timestamps, average
    calories per entry, and the five most recent matching entries. Only
    owned, non-deleted entries are considered. Used for questions like
    "when did I last eat yogurt?" or "how many times have I had pizza?"."""
    q = _str(args, "query")
    if not q or not q.strip():
        return AgentToolResult.failure("VALIDATION_ERROR", "A search term is required.")
    rows = await food_entry_repo.search_by_term(session, context.user, q.strip())
    if not rows:
        return AgentToolResult.success({
            "query": q,
            "count": 0,
            "firstEatenAt": None,
            "lastEatenAt": None,
            "averageCalories": 0,
            "recentEntries": [],
        })
    calories = [r.calories or 0 for r in rows]
    recent = sorted(rows, key=lambda r: r.eaten_at, reverse=True)[:5]
    return AgentToolResult.success({
        "query": q,
        "count": len(rows),
        "firstEatenAt": rows[0].eaten_at.isoformat() if rows[0].eaten_at else None,
        "lastEatenAt": recent[0].eaten_at.isoformat() if recent[0].eaten_at else None,
        "averageCalories": round(sum(calories) / len(calories)),
        "recentEntries": [_summary(r) for r in recent],
    })
