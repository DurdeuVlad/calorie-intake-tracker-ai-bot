import pytest_asyncio
from sqlalchemy import text

from app.db.base import session_scope


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    async with session_scope() as session:
        await session.execute(
            text(
                "TRUNCATE food_users, messaging_inbox, messaging_outbox, "
                "messaging_identities, messaging_routes, frontend_link_codes, "
                "conversation_memory, pending_nutrition_quotes, "
                "journal_change_sets, journal_change_mutations, "
                "pinned_daily_status, messaging_daily_status, report_deliveries, "
                # This has no FK relationship to food_users at all (it's a global
                # barcode cache), so CASCADE from food_users never reaches it --
                # it must be listed explicitly.
                "nutrition_source_cache "
                "CASCADE"
            )
        )
        await session.commit()
    yield
