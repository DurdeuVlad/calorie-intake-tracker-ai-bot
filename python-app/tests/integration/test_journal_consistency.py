"""Synthetic regressions using real PostgreSQL and a scripted (not live) model."""
import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.agent.journal_agent import JournalAgent
from app.agent.openai_model_client import AgentProviderUnavailableError
from app.db.base import session_scope
from app.db.models.entries import FoodEntry, FoodItem
from app.db.models.nutrition import NutritionEvidence
from app.domain.agent_types import AgentContext, AgentReply, ToolCall
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.services.journal_tool_executor import JournalToolExecutor


def call(tool_name, **args):
    return ToolCall(str(id(args)), tool_name, json.dumps(args))


async def context(session):
    user = await get_or_create_by_telegram_user_id(session, 77101, "Synthetic", "UTC")
    return AgentContext(user, "77101", "synthetic explicit journal request", started_at=datetime.now(UTC))


async def execute(executor, session, ctx, tool_name, **args):
    return await executor.execute(session, ctx, call(tool_name, **args), [])


@pytest.mark.asyncio
async def test_quantity_replacement_fresh_readback_totals_and_undo_evidence():
    executor = JournalToolExecutor()
    async with session_scope() as session:
        ctx = await context(session)
        estimate = await execute(executor, session, ctx, "estimate_food", name="buckwheat", grams=160, caloriesPer100g=180, basis="synthetic estimate")
        made = await execute(executor, session, ctx, "apply_journal_actions", actions=[{"type": "CREATE", "quoteId": estimate.data["quoteId"]}, {"type": "CREATE", "description": "other food", "calories": 230}])
        entry_id = made.data["results"][0]["entry"]["id"]
        edited = await execute(executor, session, ctx, "apply_journal_actions", actions=[{"type": "EDIT", "entryId": entry_id, "quantity": 90, "unit": "g"}])
        assert edited.data["successful"] == 1
        assert edited.data["todaySummary"]["calories"] == 392
        await session.commit()
    async with session_scope() as session:
        ctx = await context(session)
        read = await execute(executor, session, ctx, "get_entry", entryId=entry_id)
        assert read.data["entry"]["calories"] == 162
        assert read.data["entry"]["items"][0]["quantity"] == 90
        item = (await session.execute(select(FoodItem).where(FoodItem.entry_id == entry_id))).scalar_one()
        assert item.quantity_grams == Decimal(90)
        assert (await session.execute(select(NutritionEvidence))).scalars().all() == []
        undone = await execute(executor, session, ctx, "undo_last_change")
        assert undone.ok
        await session.commit()
    async with session_scope() as session:
        ctx = await context(session)
        restored = await execute(executor, session, ctx, "get_entry", entryId=entry_id)
        assert restored.data["entry"]["items"][0]["quantity"] == 160
        assert restored.data["entry"]["calories"] == 288
        evidence = (await session.execute(select(NutritionEvidence))).scalar_one()
        assert evidence.total_calories == 288
        assert evidence.quantity_grams == Decimal(160)


@pytest.mark.asyncio
async def test_absolute_count_correction_changes_existing_entry_not_duplicate():
    executor = JournalToolExecutor()
    async with session_scope() as session:
        ctx = await context(session)
        made = await execute(executor, session, ctx, "apply_journal_actions", actions=[{"type": "CREATE", "description": "four dumplings", "quantity": 4, "unit": "portion", "calories": 20}, {"type": "CREATE", "description": "baseline", "calories": 270}])
        entry_id = made.data["results"][0]["entry"]["id"]
        found = await execute(executor, session, ctx, "search_entries", query="dumplings")
        assert found.data["entries"][0]["items"][0]["quantity"] == 4
        changed = await execute(executor, session, ctx, "apply_journal_actions", actions=[{"type": "EDIT", "entryId": entry_id, "calories": 640}])
        assert changed.data["todaySummary"]["calories"] == 910
        await session.commit()
    async with session_scope() as session:
        ctx = await context(session)
        total = await execute(executor, session, ctx, "get_today_summary")
        assert total.data["calories"] == 910
        assert total.data["entries"] == 2
        # Sole multi-piece entry becomes one portion, not deleted or duplicated.
        changed = await execute(executor, session, ctx, "apply_journal_actions", actions=[{"type": "EDIT", "entryId": entry_id, "quantity": 1, "unit": "portion"}])
        assert changed.data["todaySummary"]["calories"] == 430
        assert changed.data["todaySummary"]["entries"] == 2


@pytest.mark.asyncio
async def test_direct_volume_estimate_is_never_mislabelled_user_supplied_or_grams():
    executor = JournalToolExecutor()
    async with session_scope() as session:
        ctx = await context(session)
        result = await execute(executor, session, ctx, "apply_journal_actions", actions=[{"type": "CREATE", "description": "vegetable broth", "quantity": 350, "unit": "ml", "calories": 140, "nutritionSource": "ai_estimate", "nutritionConfidence": "high", "basis": "rough recipe estimate"}])
        row = result.data["results"][0]
        assert row["nutritionSource"] == "ai_estimate"
        assert row["nutritionConfidence"] == "estimate"
        assert row["receipt"]["basis"] == "rough recipe estimate"
        item = (await session.execute(select(FoodItem))).scalar_one()
        assert item.quantity_unit == "ml"
        assert item.quantity_grams is None


class SixFoodModel:
    def __init__(self):
        self.step = 0
        self.last_exchanges = []

    async def next(self, ctx, recent, exchanges, feedback):
        self.last_exchanges = exchanges
        step = self.step
        self.step += 1
        if step == 0:
            return AgentReply(None, [call("load_instructions", topic="nutrition")])
        foods = [("rice", 140), ("egg", 90), ("tofu", 70), ("cucumber", 110), ("lentils", 220), ("kiwi", 80)]
        if 1 <= step <= 6:
            name, grams = foods[step - 1]
            return AgentReply(None, [call("estimate_food", name=name, grams=grams, caloriesPer100g=120, basis="synthetic typical food")])
        if step == 7:
            quotes = [e.result.data["quoteId"] for e in exchanges if e.call.name == "estimate_food"]
            return AgentReply(None, [call("apply_journal_actions", actions=[{"type": "CREATE", "quoteId": q} for q in quotes])])
        if step == 8:
            return AgentReply(None, [call("get_today_summary")])
        return AgentReply("All done, with an invented total of 99999", [])


@pytest.mark.asyncio
async def test_six_estimates_instruction_loading_batch_and_readback_fit_ten_calls():
    model = SixFoodModel()
    async with session_scope() as session:
        ctx = await context(session)
        agent = JournalAgent(model, JournalToolExecutor(), max_tool_calls=10)
        reply = await agent.run(session, ctx)
        assert len(model.last_exchanges) == 9
        assert reply.count("Logged:") == 6
        assert "Today: 852 kcal; 6 entries" in reply
        assert "99999" not in reply
        assert "Prepared an estimate" not in reply
        await session.commit()
    async with session_scope() as session:
        entries = (await session.execute(select(FoodEntry))).scalars().all()
        assert len(entries) == 6
        assert sum(e.calories for e in entries) == 852
        assert all(e.nutrition_source == "ai_estimate" for e in entries)


class ReplayModel:
    def __init__(self, failed=False, outage=False):
        self.calls = 0
        self.failed = failed
        self.outage = outage

    async def next(self, ctx, recent, exchanges, feedback):
        self.calls += 1
        if self.calls > 1 and self.outage:
            raise AgentProviderUnavailableError("synthetic outage")
        actions = [{"type": "CREATE", "description": "pear", "calories": 90}, {"type": "CREATE", "description": "invalid", "calories": -1}]
        if self.failed:
            actions = actions[1:]
        return AgentReply(None, [call("apply_journal_actions", actions=actions)])


@pytest.mark.asyncio
@pytest.mark.parametrize("outage", [False, True])
async def test_partial_batch_replay_or_provider_outage_has_honest_receipt(outage):
    async with session_scope() as session:
        ctx = await context(session)
        model = ReplayModel(outage=outage)
        reply = await JournalAgent(model, JournalToolExecutor(), 10).run(session, ctx)
        assert reply.count("Logged: pear") == 1
        assert "could not be applied" in reply
        assert "Prepared an estimate" not in reply
        assert len((await session.execute(select(FoodEntry))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_all_failed_retry_is_bounded_and_never_claims_success():
    async with session_scope() as session:
        ctx = await context(session)
        model = ReplayModel(failed=True)
        reply = await JournalAgent(model, JournalToolExecutor(), 10).run(session, ctx)
        assert model.calls == 3
        assert "Logged:" not in reply
        assert "could not be applied" in reply
        assert (await session.execute(select(FoodEntry))).scalars().all() == []


@pytest.mark.asyncio
async def test_exhaustion_before_mutation_does_not_request_invented_missing_detail():
    async with session_scope() as session:
        ctx = await context(session)
        reply = await JournalAgent(SixFoodModel(), JournalToolExecutor(), 3).run(session, ctx)
        assert "tool-call limit" in reply
        assert "incomplete" in reply
        assert "Not logged" in reply
        assert "Tell me if you want" not in reply
        assert (await session.execute(select(FoodEntry))).scalars().all() == []


@pytest.mark.asyncio
async def test_six_saved_estimates_then_outage_never_requests_logging_again():
    class OutageAfterBatch(SixFoodModel):
        async def next(self, ctx, recent, exchanges, feedback):
            if self.step == 8:
                raise AgentProviderUnavailableError("synthetic outage after batch")
            return await super().next(ctx, recent, exchanges, feedback)

    async with session_scope() as session:
        ctx = await context(session)
        reply = await JournalAgent(OutageAfterBatch(), JournalToolExecutor(), 10).run(session, ctx)
        assert reply.count("Logged:") == 6
        assert reply.count("(estimate)") == 6
        assert "Prepared an estimate" not in reply
        assert "Not logged" not in reply
        assert "want to log" not in reply


@pytest.mark.asyncio
async def test_quantity_basis_change_requires_calories_and_leaves_original_intact():
    executor = JournalToolExecutor()
    async with session_scope() as session:
        ctx = await context(session)
        made = await execute(executor, session, ctx, "apply_journal_actions", actions=[{"type": "CREATE", "description": "yogurt", "quantity": 120, "unit": "g", "calories": 180}])
        entry_id = made.data["results"][0]["entry"]["id"]
        invalid = await execute(executor, session, ctx, "apply_journal_actions", actions=[{"type": "EDIT", "entryId": entry_id, "quantity": 1, "unit": "portion"}])
        assert invalid.data["successful"] == 0
        assert invalid.data["todaySummary"]["calories"] == 180
        read = await execute(executor, session, ctx, "get_entry", entryId=entry_id)
        assert read.data["entry"]["items"][0]["quantity"] == 120
        assert read.data["entry"]["items"][0]["unit"] == "g"


@pytest.mark.asyncio
async def test_expired_quote_failure_keeps_owned_food_identity_and_index():
    from datetime import timedelta

    from app.db.models.nutrition import PendingNutritionQuote

    executor = JournalToolExecutor()
    async with session_scope() as session:
        ctx = await context(session)
        estimated = await execute(executor, session, ctx, "estimate_food", name="berry pudding", grams=95, caloriesPer100g=130)
        quote = (await session.execute(select(PendingNutritionQuote))).scalar_one()
        quote.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        result = await execute(executor, session, ctx, "apply_journal_actions", actions=[{"type": "CREATE", "quoteId": estimated.data["quoteId"]}])
        row = result.data["results"][0]
        assert row["ok"] is False
        assert row["actionIndex"] == 1
        assert row["requestedDescription"] == "berry pudding"
        assert result.data["successful"] == 0


@pytest.mark.asyncio
async def test_all_failed_then_successful_retry_has_unambiguous_final_receipt():
    class RetryOnce:
        def __init__(self):
            self.step = 0

        async def next(self, ctx, recent, exchanges, feedback):
            self.step += 1
            if self.step <= 2:
                return AgentReply(None, [call("apply_journal_actions", replyLanguage="ro", actions=[{"type": "CREATE", "description": "pară", "calories": -1 if self.step == 1 else 90}])])
            return AgentReply("an invented result", [])

    async with session_scope() as session:
        ctx = await context(session)
        reply = await JournalAgent(RetryOnce(), JournalToolExecutor(), 10).run(session, ctx)
        assert "Notat: pară" in reply
        assert "90 kcal" in reply
        assert "nu s-a aplicat" not in reply
        assert "an invented result" not in reply
        assert len((await session.execute(select(FoodEntry))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_mixed_gram_volume_six_food_case_fits_budget_without_unit_fabrication():
    class MixedSix(SixFoodModel):
        async def next(self, ctx, recent, exchanges, feedback):
            if self.step <= 5:
                return await super().next(ctx, recent, exchanges, feedback)
            self.last_exchanges = exchanges
            step = self.step
            self.step += 1
            if step == 6:
                quotes = [e.result.data["quoteId"] for e in exchanges if e.call.name == "estimate_food"]
                actions = [{"type": "CREATE", "quoteId": q} for q in quotes]
                actions.append({"type": "CREATE", "description": "vegetable broth", "quantity": 350, "unit": "ml", "calories": 140, "nutritionSource": "ai_estimate", "basis": "assuming light broth at 40 kcal per 100 ml"})
                return AgentReply(None, [call("apply_journal_actions", replyLanguage="en", actions=actions)])
            if step == 7:
                return AgentReply(None, [call("get_today_summary")])
            return AgentReply("done", [])

    model = MixedSix()
    async with session_scope() as session:
        ctx = await context(session)
        reply = await JournalAgent(model, JournalToolExecutor(), 10).run(session, ctx)
        assert len(model.last_exchanges) == 8
        assert reply.count("Logged:") == 6
        assert "Today: 896 kcal; 6 entries" in reply
        assert "assuming light broth at 40 kcal per 100 ml" in reply
        await session.commit()
    async with session_scope() as session:
        items = (await session.execute(select(FoodItem))).scalars().all()
        assert len(items) == 6
        volume = next(item for item in items if item.quantity_unit == "ml")
        assert volume.quantity == Decimal(350)
        assert volume.quantity_grams is None
        assert volume.nutrition_source == "ai_estimate"
        assert volume.nutrition_confidence == "estimate"


@pytest.mark.asyncio
async def test_failed_foreign_quote_does_not_disclose_its_owned_identity():
    executor = JournalToolExecutor()
    async with session_scope() as session:
        ctx = await context(session)
        other = await get_or_create_by_telegram_user_id(session, 77102, "Other synthetic user", "UTC")
        foreign = AgentContext(other, "77102", "synthetic", started_at=ctx.started_at)
        estimated = await execute(executor, session, foreign, "estimate_food", name="foreign household recipe", grams=95, caloriesPer100g=130)
        result = await execute(executor, session, ctx, "apply_journal_actions", actions=[{"type": "CREATE", "quoteId": estimated.data["quoteId"]}])
        row = result.data["results"][0]
        assert row["ok"] is False
        assert row["requestedDescription"] == "item 1"
        assert "foreign household recipe" not in json.dumps(result.data)
        assert (await session.execute(select(FoodEntry))).scalars().all() == []


@pytest.mark.asyncio
async def test_receipt_language_cannot_override_mutation_validation():
    executor = JournalToolExecutor()
    async with session_scope() as session:
        ctx = await context(session)
        result = await execute(executor, session, ctx, "apply_journal_actions", replyLanguage="ro", actions=[{"type": "CREATE", "description": "invalid", "calories": -1}])
        assert result.data["successful"] == 0
        assert result.data["replyLanguage"] == "ro"
        invalid_language = await execute(executor, session, ctx, "apply_journal_actions", replyLanguage="xx", actions=[{"type": "CREATE", "description": "pear", "calories": 90}])
        assert invalid_language.ok is False
        assert (await session.execute(select(FoodEntry))).scalars().all() == []
