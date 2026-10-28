"""Round-two synthetic receipt boundary checks; no provider or database."""
import json

from app.agent.journal_agent import JournalAgent
from app.domain.agent_types import AgentExchange, AgentToolResult, ToolCall


def exchange(name, data, arguments=None):
    return AgentExchange(ToolCall(name, name, json.dumps(arguments or {})), AgentToolResult.success(data))


def selected(quote, name):
    return exchange("select_packaged_food", {"quoteId": quote, "item": {"name": name, "totalCalories": 140}})


def mutation(rows, **data):
    return exchange("apply_journal_actions", {"successful": sum(row["ok"] for row in rows), "results": rows, **data}, {"actions": [{"quoteId": "saved-quote", "type": "CREATE"}]})


def render(exchanges):
    return JournalAgent(None, None, 10)._fallback_receipt(exchanges)


def test_consumed_selection_is_not_also_reported_not_logged():
    receipt = render([selected("saved-quote", "synthetic cereal"), mutation([{"type": "CREATE", "ok": True, "description": "synthetic cereal", "calories": 140}])])
    assert "Logged: synthetic cereal" in receipt
    assert "Selected" not in receipt
    assert "Not logged" not in receipt


def test_genuinely_unsubmitted_selection_is_identified_as_not_logged():
    receipt = render([selected("saved-quote", "synthetic cereal"), selected("unsaved-quote", "synthetic yogurt"), mutation([{"type": "CREATE", "ok": True, "description": "synthetic cereal", "calories": 140}])])
    assert "Logged: synthetic cereal" in receipt
    assert "Selected synthetic yogurt. Not logged." in receipt
    assert "Selected synthetic cereal" not in receipt


def test_selection_without_any_mutation_still_says_not_logged():
    assert "Selected synthetic cereal. Not logged." in render([selected("saved-quote", "synthetic cereal")])


def test_replacement_quantity_is_authoritative_and_old_name_is_only_a_label():
    receipt = render([mutation([{"type": "EDIT", "ok": True, "description": "four dumplings", "calories": 160, "receipt": {"quantity": 1, "unit": "portion", "quantityReplaced": True}}])])
    assert "replacement quantity: 1 portion" in receipt
    assert "entry label: «four dumplings»" in receipt
    assert "Updated: four dumplings" not in receipt


def test_romanian_copy_uses_same_authoritative_facts_and_today_label():
    receipt = render([mutation([{"type": "EDIT", "ok": True, "description": "găluște", "calories": 160, "date": "2026-10-26", "receipt": {"quantity": 1, "unit": "portion", "quantityReplaced": True}}], replyLanguage="ro", todaySummary={"calories": 430, "entries": 2}, undoAvailable=True)])
    assert "Actualizat: cantitate nouă: 1 portion" in receipt
    assert "160 kcal" in receipt
    assert "2026-10-26" in receipt
    assert "Azi: 430 kcal; 2 intrări" in receipt
    assert "Trimite Undo" in receipt
    assert "Today:" not in receipt


def test_failed_food_is_named_and_indexed():
    receipt = render([mutation([{"type": "CREATE", "ok": False, "actionIndex": 6, "requestedDescription": "berry pudding", "message": "expired quote"}])])
    assert "CREATE #6 (berry pudding): could not be applied" in receipt


def test_direct_volume_estimate_shows_concise_assumption():
    receipt = render([mutation([{"type": "CREATE", "ok": True, "description": "vegetable broth", "calories": 140, "nutritionSource": "ai_estimate", "receipt": {"quantity": 350, "unit": "ml", "basis": "assuming a light recipe at 40 kcal per 100 ml"}}])])
    assert "(estimate)" in receipt
    assert "basis: assuming a light recipe at 40 kcal per 100 ml" in receipt


def test_successful_retry_keeps_clearly_labelled_prior_failures():
    receipt = render([mutation([{"type": "CREATE", "ok": False, "actionKey": "name:pear", "requestedDescription": "pear", "message": "invalid"}, {"type": "CREATE", "ok": False, "actionKey": "name:kiwi", "requestedDescription": "kiwi", "message": "invalid"}]), mutation([{"type": "CREATE", "ok": True, "actionKey": "name:pear", "description": "pear", "calories": 90}])])
    assert "Logged: pear" in receipt
    assert "(pear): could not" in receipt
    assert "Attempt 1 (earlier attempt)" in receipt
    assert "Attempt 2 (latest attempt)" in receipt
    assert "(kiwi): could not" in receipt


def test_same_name_distinct_portions_across_attempts_keep_both_failed_results():
    receipt = render([mutation([
        {"type": "CREATE", "ok": False, "actionKey": "name:rice", "actionIndex": 1, "requestedDescription": "rice", "message": "first portion invalid"},
        {"type": "CREATE", "ok": False, "actionKey": "name:rice", "actionIndex": 2, "requestedDescription": "rice", "message": "second portion invalid"},
    ]), mutation([{"type": "CREATE", "ok": True, "actionKey": "name:rice", "description": "rice", "calories": 100}])])
    assert "Attempt 1 (earlier attempt)" in receipt
    assert "Attempt 2 (latest attempt)" in receipt
    assert receipt.count("could not be applied") == 2
    assert "CREATE #1 (rice)" in receipt
    assert "CREATE #2 (rice)" in receipt
    assert receipt.count("Logged: rice") == 1


def test_same_batch_same_name_success_never_hides_failed_sibling():
    receipt = render([mutation([
        {"type": "CREATE", "ok": True, "actionKey": "name:yogurt", "actionIndex": 1, "description": "yogurt", "calories": 90},
        {"type": "CREATE", "ok": False, "actionKey": "name:yogurt", "actionIndex": 2, "requestedDescription": "yogurt", "message": "invalid portion"},
    ])])
    assert "Attempt 1" in receipt
    assert "Logged: yogurt" in receipt
    assert "CREATE #2 (yogurt): could not be applied" in receipt


def test_edit_success_and_move_failure_for_same_entry_are_both_preserved():
    receipt = render([mutation([
        {"type": "EDIT", "ok": True, "actionKey": "entry:7", "actionIndex": 1, "description": "lunch", "calories": 250},
        {"type": "MOVE", "ok": False, "actionKey": "entry:7", "actionIndex": 2, "requestedDescription": "lunch", "message": "future date rejected"},
    ])])
    assert "Updated: lunch" in receipt
    assert "MOVE #2 (lunch): could not be applied" in receipt
