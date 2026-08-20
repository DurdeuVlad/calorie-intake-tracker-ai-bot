"""Regression test for a real bug found and fixed in the Java predecessor:
recording conversation memory at the wrong call site (inside the identity
bootstrap helper, which internally re-invoked the full command/agent handler
just to provision a first-time user) caused an EXTRA, spurious turn to be
recorded alongside the real one. This Python port avoids the whole class of
bug by construction: identity bootstrap creates the FoodUser/MessagingIdentity
rows directly and never calls journal.handle() internally, so there is only
ever one call site that can record memory. Prove a brand-new user's very
first message -- command or not -- records exactly one user+assistant pair,
never two."""

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db.base import session_scope
from app.db.models.conversation import ConversationMemory
from app.messaging import inbox_worker
from app.messaging.inbound_message import InboundMessage


@pytest.fixture(autouse=True)
def _allow_test_user(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(type(settings), "allowed_telegram_user_id_set", property(lambda self: {"777"}))
    yield


@pytest.mark.asyncio
async def test_first_message_from_a_brand_new_user_records_exactly_one_pair_even_for_a_slash_command():
    inbound = InboundMessage(
        provider="telegram",
        event_id="evt-first",
        user_id="777",
        conversation_id="777",
        display_name="Brand New User",
        language_code="en",
        text="/help",
        caption=None,
    )
    async with session_scope() as session:
        from app.messaging import ingress

        await ingress.accept(session, inbound)

    processed = await inbox_worker.process_one()
    assert processed is True

    async with session_scope() as session:
        rows = (await session.execute(select(ConversationMemory))).scalars().all()
    # Exactly one user+assistant pair -- if the bootstrap helper ever regressed
    # to calling journal.handle() internally (the Java bug), this would be 4.
    assert len(rows) == 2
    roles = sorted(r.role for r in rows)
    assert roles == ["assistant", "user"]


@pytest.mark.asyncio
async def test_a_real_conversational_turn_records_exactly_one_user_assistant_pair():
    inbound = InboundMessage(
        provider="telegram",
        event_id="evt-second",
        user_id="777",
        conversation_id="777",
        display_name="Brand New User",
        language_code="en",
        text="how many calories today",
        caption=None,
    )
    async with session_scope() as session:
        from app.messaging import ingress

        await ingress.accept(session, inbound)

    await inbox_worker.process_one()

    async with session_scope() as session:
        rows = (await session.execute(select(ConversationMemory))).scalars().all()
    assert len(rows) == 2
    roles = sorted(r.role for r in rows)
    assert roles == ["assistant", "user"]
