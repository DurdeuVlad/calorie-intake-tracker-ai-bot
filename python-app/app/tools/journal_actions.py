"""Journal mutation tools: apply_journal_actions (CREATE/EDIT/MOVE/DELETE) and undo_last_change."""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.db.constraints import (
    MAX_ACTIONS_PER_BATCH,
    MAX_CALORIES,
    MAX_DATE_CHARS,
    MAX_PROVIDER_CHARS,
    MAX_QUANTITY,
    MAX_TEXT_CHARS,
    MAX_UNIT_CHARS,
    MAX_WEB_SEARCH_RESULTS,
    MIN_CALORIES,
    UNDO_WINDOW,
)
from app.db.models.entries import FoodEntry, FoodItem
from app.db.models.journal_changes import JournalChangeSet
from app.db.models.nutrition import NutritionEvidence, PendingNutritionQuote
from app.domain import journal_entry_snapshot as snapshot
from app.domain.agent_types import AgentToolFailure, AgentToolResult
from app.domain.quantity_unit import QuantityUnit
from app.repositories import (
    food_entry_repo,
    food_item_repo,
    food_user_repo,
    journal_change_set_repo,
    nutrition_evidence_repo,
    pending_nutrition_quote_repo,
)
from app.tools.shared import (
    MAX_DATABASE_ID,
    ValidationError,
    _normalize,
    _optional_int,
    _quantity_number,
    _quantity_unit,
    _quote_id,
    _resolve_meal_instant,
    _search_date,
    _summary,
    _text,
    _unverified_source_claim,
    _valid_calories_per_100g,
)

logger = logging.getLogger(__name__)


async def _settings_for(executor, session, context):
    return await executor._settings_for(session, context)


async def _evidence_for_items(session, items: list[FoodItem]):
    return await nutrition_evidence_repo.find_by_food_item_ids(session, [item.id for item in items])


async def _refresh_daily_status_safely(executor, session, context) -> None:
    """Do not let optional pinned-status bookkeeping roll back journal state."""
    try:
        async with session.begin_nested():
            await executor.refresh_daily_status(session, context.user, context.chat_id)
    except Exception:
        logger.exception("Pinned daily status refresh failed for user_id=%s", context.user.id)


async def _owned_entry(session, context, args) -> FoodEntry:
    if "entryId" not in args:
        raise ValidationError("An entry ID is required.")
    entry_id = _optional_int(args, "entryId", min_value=1, max_value=MAX_DATABASE_ID)
    if entry_id is None:
        raise ValidationError("An entry ID is required.")
    entry = await food_entry_repo.find_by_id_and_user(session, entry_id, context.user, for_update=True)
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
    description = _text(args, "description", MAX_TEXT_CHARS) or _text(args, "name", MAX_TEXT_CHARS)
    calories = _optional_int(args, "calories", min_value=MIN_CALORIES, max_value=MAX_CALORIES)
    requested_source = _text(args, "nutritionSource", MAX_PROVIDER_CHARS)
    source = _normalize(requested_source, "manual", {"manual", "private", "open_food_facts", "open_food_facts_estimate", "ai_estimate", "mixed"})
    confidence = _normalize(_text(args, "nutritionConfidence", MAX_PROVIDER_CHARS), "high" if source == "manual" else "estimate", {"high", "estimate", "unknown"})
    quantity = _quantity_number(args, "quantity")
    unit = _quantity_unit(_text(args, "unit", MAX_UNIT_CHARS), quantity)
    consumed: list[PendingNutritionQuote] = []
    created_evidence: dict[int, NutritionEvidence] = {}
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
        if quote.quote_type not in {"PACKAGED_MATCH", "AI_ESTIMATE"}:
            raise ValidationError("The selected nutrition result has an unsupported type.")
        if not _valid_calories_per_100g(quote.calories_per_100g):
            raise ValidationError("The selected nutrition result has invalid calorie data.")
        quoted = executor._quote_item(quote)
        calories = quoted.total_calories
        if calories > MAX_CALORIES:
            raise ValidationError(f"The selected nutrition result exceeds the {MAX_CALORIES} kcal journal limit.")
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

    if not description or not description.strip():
        raise ValidationError("A description is required unless the selected quote supplies one.")
    if calories is None or calories < MIN_CALORIES or calories > MAX_CALORIES:
        raise ValidationError(f"Calories must be between {MIN_CALORIES} and {MAX_CALORIES}.")
    if quantity is not None and (quantity <= 0 or quantity > float(MAX_QUANTITY)):
        raise ValidationError("Quantity must be positive.")

    eaten_at = _resolve_meal_instant(context, timezone_name, _text(args, "date", MAX_DATE_CHARS), _text(args, "localTime", MAX_DATE_CHARS))
    entry = FoodEntry(user_id=context.user.id, original_message=description, eaten_at=eaten_at, calories=calories, nutrition_source=source, confidence=confidence, created_at=now)
    session.add(entry)
    await session.flush()
    quantity_value = Decimal(str(quantity)) if quantity is not None else None
    item = FoodItem(
        entry_id=entry.id,
        name=description,
        quantity_grams=quantity_value if unit == QuantityUnit.G.value else None,
        quantity=quantity_value,
        quantity_unit=unit,
        calories=calories,
        nutrition_source=source,
        nutrition_confidence=confidence,
    )
    session.add(item)
    await session.flush()

    for quote in consumed:
        if quote.quote_type == "PACKAGED_MATCH":
            await executor._cache_selected(session, quote)
            created_evidence[item.id] = executor._record_packaged_evidence(session, entry, item, quote, now)
        elif quote.quote_type == "AI_ESTIMATE":
            created_evidence[item.id] = executor._record_ai_estimate_evidence(session, entry, item, quote, now)
        await session.delete(quote)

    await session.flush()
    after = snapshot.capture(entry, [item], created_evidence)
    if change_set is not None:
        change_set.add_mutation("CREATE", None, after)
    if unverified_source:
        receipt["basis"] = "unverified source label ignored; calories supplied in the message"
    elif source == "manual":
        receipt["basis"] = "user-provided calories"
    if derivation is None and receipt.get("caloriesPer100g") is not None and quantity is not None and unit == "g":
        per_100g = receipt["caloriesPer100g"]
        derivation = f"{quantity} g × {per_100g} kcal/100 g = {calories} kcal"
    undo_deadline = now + UNDO_WINDOW if change_set is not None else None
    return _action_success(
        "CREATE", entry, timezone_name, receipt,
        undo_deadline=undo_deadline, derivation=derivation,
        source_url=source_url, source_name=source_name,
    )


async def _edit_action(executor, session, context, args, change_set, now, timezone_name) -> dict[str, Any]:
    entry = await _owned_entry(session, context, args)
    current = await food_item_repo.find_by_entry(session, entry)
    evidence_by_item_id = await _evidence_for_items(session, current)
    before = snapshot.capture(entry, current, evidence_by_item_id)
    description = _text(args, "description", MAX_TEXT_CHARS) or entry.original_message
    if not description.strip():
        raise ValidationError("A description is required.")
    calories = _optional_int(args, "calories", min_value=MIN_CALORIES, max_value=MAX_CALORIES)
    if calories is None:
        calories = entry.calories
    if calories is None or calories < MIN_CALORIES or calories > MAX_CALORIES:
        raise ValidationError(f"Calories must be between {MIN_CALORIES} and {MAX_CALORIES}.")
    entry.revise(description, calories)
    executor._synchronize_items_after_edit(current, description, calories)
    after = snapshot.capture(entry, current, evidence_by_item_id)
    if change_set is not None:
        change_set.add_mutation("EDIT", before, after)
    undo_deadline = now + UNDO_WINDOW if change_set is not None else None
    return _action_success("EDIT", entry, timezone_name, undo_deadline=undo_deadline)


async def _move_action(executor, session, context, args, change_set, now, timezone_name) -> dict[str, Any]:
    entry = await _owned_entry(session, context, args)
    requested_date = _text(args, "date", MAX_DATE_CHARS)
    if not requested_date or not requested_date.strip():
        raise ValidationError("A date is required when moving a journal entry.")
    current = await food_item_repo.find_by_entry(session, entry)
    evidence_by_item_id = await _evidence_for_items(session, current)
    before = snapshot.capture(entry, current, evidence_by_item_id)
    new_when = _resolve_meal_instant(context, timezone_name, requested_date, _text(args, "localTime", MAX_DATE_CHARS), entry.eaten_at)
    entry.move_to(new_when, context.started_at)
    after = snapshot.capture(entry, current, evidence_by_item_id)
    if change_set is not None:
        change_set.add_mutation("MOVE", before, after)
    undo_deadline = now + UNDO_WINDOW if change_set is not None else None
    return _action_success("MOVE", entry, timezone_name, undo_deadline=undo_deadline)


async def _delete_action(executor, session, context, args, change_set, now, timezone_name) -> dict[str, Any]:
    entry = await _owned_entry(session, context, args)
    current = await food_item_repo.find_by_entry(session, entry)
    evidence_by_item_id = await _evidence_for_items(session, current)
    before = snapshot.capture(entry, current, evidence_by_item_id)
    entry.mark_deleted(now)
    after = snapshot.capture(entry, current, evidence_by_item_id)
    if change_set is not None:
        change_set.add_mutation("DELETE", before, after)
    undo_deadline = now + UNDO_WINDOW if change_set is not None else None
    return _action_success("DELETE", entry, timezone_name, undo_deadline=undo_deadline)


async def apply_journal_actions(executor, session, context, args, todos) -> AgentToolResult:
    requested = args.get("actions")
    if not isinstance(requested, list) or not requested:
        return AgentToolResult.failure("VALIDATION_ERROR", "At least one journal action is required.")
    if len(requested) > MAX_ACTIONS_PER_BATCH:
        return AgentToolResult.failure(
            "VALIDATION_ERROR", f"A message may contain at most {MAX_ACTIONS_PER_BATCH} journal actions."
        )

    await food_user_repo.lock_for_journal_mutation(session, context.user.id)
    settings = await executor._settings_for(session, context)
    now = datetime.now(UTC)
    await journal_change_set_repo.delete_expired(session, now)
    change_set = JournalChangeSet(user_id=context.user.id, created_at=now, expires_at=now + UNDO_WINDOW)

    results: list[dict[str, Any]] = []
    changed = 0
    for raw in requested:
        if not isinstance(raw, dict):
            results.append(_action_failure("ACTION", "Invalid journal action."))
            continue
        raw_type = raw.get("type")
        if raw_type is None:
            action_type = "ACTION"
        elif not isinstance(raw_type, str):
            results.append(_action_failure("ACTION", "The action type must be text."))
            continue
        else:
            action_type = raw_type.upper()
        try:
            if action_type == "CREATE":
                result = await _create_action(executor, session, context, raw, change_set, now, settings.timezone)
            elif action_type == "EDIT":
                result = await _edit_action(executor, session, context, raw, change_set, now, settings.timezone)
            elif action_type == "MOVE":
                result = await _move_action(executor, session, context, raw, change_set, now, settings.timezone)
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
        await _refresh_daily_status_safely(executor, session, context)

    return AgentToolResult.success(
        {"results": results, "successful": changed, "failed": len(results) - changed, "undoAvailable": changed > 0}
    )


async def undo_last_change(executor, session, context, args, todos) -> AgentToolResult:
    try:
        async with session.begin_nested():
            return await _undo_last_change(executor, session, context, args, todos)
    except (ArithmeticError, KeyError, TypeError, ValueError) as failure:
        logger.warning("Malformed journal snapshot prevented Undo for user_id=%s: %s", context.user.id, type(failure).__name__)
        return AgentToolResult.failure("CONFLICT", "The latest journal change can no longer be undone safely.")


async def _undo_last_change(executor, session, context, args, todos) -> AgentToolResult:
    await food_user_repo.lock_for_journal_mutation(session, context.user.id)
    now = datetime.now(UTC)
    change_set = await journal_change_set_repo.find_first_undoable(session, context.user, now)
    if change_set is None:
        return AgentToolResult.failure("NOT_FOUND", "There is no recent journal change to undo.")
    mutations = list(reversed(change_set.mutations))
    resolved_entries: list[tuple[Any, FoodEntry]] = []
    validated_entry_ids: set[int] = set()
    for mutation in mutations:
        before = mutation.before_state
        after = mutation.after_state
        invalid_snapshot = (
            not isinstance(after, dict)
            or (before is not None and not isinstance(before, dict))
            or (mutation.action_type != "CREATE" and before is None)
            or (isinstance(after, dict) and "entryId" not in after)
            or (isinstance(before, dict) and "entryId" not in before)
        )
        if invalid_snapshot:
            raise AgentToolFailure(
                AgentToolResult.failure("CONFLICT", "The latest journal change can no longer be undone safely.")
            )
        entry_id = before["entryId"] if before is not None else after["entryId"]
        entry = await food_entry_repo.find_by_id_and_user(
            session, entry_id, context.user, include_deleted=True, for_update=True
        )
        if entry is None:
            raise AgentToolFailure(
                AgentToolResult.failure("CONFLICT", "The latest journal change can no longer be undone safely.")
            )
        if entry_id not in validated_entry_ids:
            current_items = await food_item_repo.find_by_entry(session, entry)
            after_items = after.get("items")
            include_evidence = isinstance(after_items, list) and any(
                isinstance(item_snapshot, dict) and "nutritionEvidence" in item_snapshot
                for item_snapshot in after_items
            )
            evidence_by_item_id = await _evidence_for_items(session, current_items) if include_evidence else None
            current = snapshot.capture(entry, current_items, evidence_by_item_id)
            if current != after:
                raise AgentToolFailure(
                    AgentToolResult.failure("CONFLICT", "The latest journal change has been modified and cannot be undone safely.")
                )
            validated_entry_ids.add(entry_id)
        resolved_entries.append((mutation, entry))

    if not change_set.is_undoable_at(now):
        raise AgentToolFailure(
            AgentToolResult.failure("NOT_FOUND", "The latest journal change can no longer be undone.")
        )
    try:
        change_set.mark_undone(now)
    except ValueError as failure:
        raise AgentToolFailure(
            AgentToolResult.failure("NOT_FOUND", "The latest journal change can no longer be undone.")
        ) from failure

    undone_actions: list[dict[str, Any]] = []
    for mutation, entry in resolved_entries:
        before = mutation.before_state
        after = mutation.after_state
        if mutation.action_type == "CREATE":
            entry.mark_deleted(now)
            undone_actions.append({
                "type": "CREATE",
                "description": after["originalMessage"] if after else "entry",
                "calories": after["calories"] if after else None,
            })
            continue
        executor._restore_from(entry, before)
        current_items = await food_item_repo.find_by_entry(session, entry)
        current_evidence = await _evidence_for_items(session, current_items)
        for evidence in current_evidence.values():
            session.expunge(evidence)
        await food_item_repo.delete_by_entry(session, entry)
        await session.flush()
        item_snapshots = before.get("items", [])
        if not isinstance(item_snapshots, list) or any(not isinstance(item_snapshot, dict) for item_snapshot in item_snapshots):
            raise ValueError("Journal item snapshot must be a list of objects")
        restoration_snapshots: list[dict[str, Any]] = []
        for item_snapshot in item_snapshots:
            if "nutritionEvidence" in item_snapshot:
                restoration_snapshots.append(item_snapshot)
                continue
            evidence = current_evidence.get(item_snapshot.get("itemId"))
            restoration_snapshots.append(
                {
                    **item_snapshot,
                    "nutritionEvidence": [snapshot.capture_evidence(evidence)] if evidence is not None else [],
                }
            )
        restored_items = [snapshot.recreate_item_for(entry, item_snapshot) for item_snapshot in restoration_snapshots]
        session.add_all(restored_items)
        await session.flush()
        for item_snapshot, restored_item in zip(restoration_snapshots, restored_items, strict=True):
            session.add_all(snapshot.recreate_evidence_for(entry, restored_item, item_snapshot))
        await session.flush()
        undone_actions.append({
            "type": mutation.action_type,
            "description": before["originalMessage"] if before else "entry",
            "calories": before["calories"] if before else None,
        })
    await _refresh_daily_status_safely(executor, session, context)
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
    reference = _search_date(context, _text(args, "date", MAX_DATE_CHARS), today)
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
    q = _text(args, "query", MAX_TEXT_CHARS)
    date_arg = _text(args, "date", MAX_DATE_CHARS)
    from_arg = _text(args, "fromDate", MAX_DATE_CHARS)
    to_arg = _text(args, "toDate", MAX_DATE_CHARS)
    zone = ZoneInfo(settings.timezone)
    today = context.started_at.astimezone(zone).date()

    rows = await executor._search_entries_impl(session, context, q, date_arg, from_arg, to_arg, zone, today)
    return AgentToolResult.success({"entries": [_summary(r) for r in rows[:10]]})


async def get_entry(executor, session, context, args, todos) -> AgentToolResult:
    from app.tools.shared import _int_required

    entry = await food_entry_repo.find_by_id_and_user(
        session,
        _int_required(args, "entryId", min_value=1, max_value=MAX_DATABASE_ID),
        context.user,
    )
    if entry is None:
        return AgentToolResult.failure("NOT_FOUND", "No matching journal entry exists.")
    return AgentToolResult.success({"entry": _summary(entry)})


async def search_food_history(executor, session, context, args, todos) -> AgentToolResult:
    """Search the caller's full journal history for a food term and return
    aggregated info: total count, first/last eaten timestamps, average
    calories per entry, and the five most recent matching entries. Only
    owned, non-deleted entries are considered. Used for questions like
    "when did I last eat yogurt?" or "how many times have I had pizza?"."""
    q = _text(args, "query", MAX_TEXT_CHARS)
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
    recent = sorted(rows, key=lambda r: r.eaten_at, reverse=True)[:MAX_WEB_SEARCH_RESULTS]
    return AgentToolResult.success({
        "query": q,
        "count": len(rows),
        "firstEatenAt": rows[0].eaten_at.isoformat() if rows[0].eaten_at else None,
        "lastEatenAt": recent[0].eaten_at.isoformat() if recent[0].eaten_at else None,
        "averageCalories": round(sum(calories) / len(calories)),
        "recentEntries": [_summary(r) for r in recent],
    })
