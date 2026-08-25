import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.agent.tool_schemas import tool_definitions
from app.db.models.entries import FoodEntry, FoodItem
from app.db.models.nutrition import NutritionEvidence, PendingNutritionQuote
from app.domain.agent_types import AgentContext
from app.services.journal_tool_executor import JournalToolExecutor, ValidationError


class _RecordingSession:
    def __init__(self) -> None:
        self.added = []

    def add(self, value) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        for index, value in enumerate(self.added, start=1):
            if isinstance(value, FoodEntry) and value.id is None:
                value.id = 100 + index
            if isinstance(value, FoodItem) and value.id is None:
                value.id = 200 + index

    async def delete(self, value) -> None:
        return None


def test_selected_packaged_quote_is_copied_to_durable_server_owned_evidence():
    now = datetime.now(UTC)
    quote_id = uuid.uuid4()
    quote = PendingNutritionQuote(
        quote_id=quote_id,
        batch_id=uuid.uuid4(),
        user_id=1,
        quote_type="PACKAGED_MATCH",
        product_name="Cola",
        brand="Acme",
        grams=Decimal(330),
        calories_per_100g=42,
        barcode="5941234567890",
        source_url="https://world.openfoodfacts.org/product/5941234567890",
        source_query="cola acme",
        created_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    entry = FoodEntry(id=11)
    item = FoodItem(id=22)
    session = _RecordingSession()

    JournalToolExecutor()._record_packaged_evidence(session, entry, item, quote, now)

    assert len(session.added) == 1
    evidence = session.added[0]
    assert isinstance(evidence, NutritionEvidence)
    assert evidence.food_entry_id == 11
    assert evidence.food_item_id == 22
    assert evidence.selected_quote_id == quote_id
    assert evidence.provider == "open_food_facts"
    assert evidence.source_url == quote.source_url
    assert evidence.source_query == "cola acme"
    assert evidence.selected_candidate == '{"barcode":"5941234567890","brand":"Acme","name":"Cola"}'
    assert evidence.quantity_grams == Decimal(330)
    assert evidence.calories_per_100g == 42
    assert evidence.total_calories == 139
    assert evidence.derivation == "round(330 g × 42 kcal / 100 g) = 139 kcal"
    assert evidence.confidence == "high"
    assert evidence.captured_at == now


def test_journal_action_only_accepts_server_issued_quote_ids_for_provenance():
    definitions = {tool["function"]["name"]: tool["function"] for tool in tool_definitions()}
    action = definitions["apply_journal_actions"]["parameters"]["properties"]["actions"]["items"]

    assert "quoteId" in action["properties"]
    assert "sourceUrl" not in action["properties"]
    assert "server-issued quoteId" in definitions["apply_journal_actions"]["description"]


@pytest.mark.asyncio
async def test_model_cannot_claim_open_food_facts_without_a_server_quote():
    executor = JournalToolExecutor()
    with pytest.raises(ValidationError, match="server-issued quoteId"):
        await executor._create_action(
            None,
            None,
            {"description": "claimed product", "calories": 100, "nutritionSource": "open_food_facts"},
            None,
            datetime.now(UTC),
            "Europe/Bucharest",
        )


@pytest.mark.asyncio
async def test_forged_private_source_is_stored_as_manual_unverified_value():
    session = _RecordingSession()
    context = AgentContext(
        user=type("User", (), {"id": 1})(), chat_id="1", romanian=False, message="family soup 250 kcal"
    )

    result = await JournalToolExecutor()._create_action(
        session,
        context,
        {"description": "family soup", "calories": 250, "nutritionSource": "private"},
        None,
        context.started_at,
        "Europe/Bucharest",
    )

    entry = next(value for value in session.added if isinstance(value, FoodEntry))
    assert entry.nutrition_source == "manual"
    assert entry.confidence == "unknown"
    assert result["nutritionSource"] == "manual"
    assert result["receipt"]["basis"] == "unverified source label ignored; calories supplied in the message"


@pytest.mark.asyncio
async def test_server_issued_ai_quote_keeps_its_estimate_provenance(monkeypatch):
    now = datetime.now(UTC)
    quote = PendingNutritionQuote(
        quote_id=uuid.uuid4(), batch_id=uuid.uuid4(), user_id=1, quote_type="AI_ESTIMATE",
        product_name="curry", grams=Decimal(250), calories_per_100g=200,
        estimate_basis="visible bowl portion", created_at=now, expires_at=now + timedelta(minutes=30),
    )

    async def quote_lookup(session, quote_id, user, lookup_now):
        return quote

    monkeypatch.setattr(
        "app.services.journal_tool_executor.pending_nutrition_quote_repo.lock_owned_active", quote_lookup
    )
    session = _RecordingSession()
    context = AgentContext(user=type("User", (), {"id": 1})(), chat_id="1", romanian=False, message="curry")
    result = await JournalToolExecutor()._create_action(
        session, context, {"description": "curry", "quoteId": str(quote.quote_id)}, None, context.started_at, "Europe/Bucharest"
    )

    entry = next(value for value in session.added if isinstance(value, FoodEntry))
    assert entry.nutrition_source == "ai_estimate"
    assert result["receipt"] == {
        "quantity": 250.0, "unit": "g", "caloriesPer100g": 200, "basis": "visible bowl portion"
    }
