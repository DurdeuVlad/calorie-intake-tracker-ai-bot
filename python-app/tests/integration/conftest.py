import pytest_asyncio
from sqlalchemy import text

from app.db.base import session_scope


async def _truncate_test_tables() -> None:
    async with session_scope() as session:
        await session.execute(
            text(
                "TRUNCATE food_users, telegram_access_grants, messaging_inbox, messaging_outbox, "
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


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    # Truncate both before AND after: cleaning up only before each test leaves
    # the LAST test's rows sitting in the database once the whole suite exits.
    # `foodjournal` is also the database docker-compose's `app` service and
    # manual/dev testing point at, so a leftover row (e.g. a stray
    # provider="terminal" daily-status row) doesn't just affect other tests --
    # it can trip production-shaped code paths (frontend registries that never
    # register a "terminal" provider) the next time the real app starts.
    await _truncate_test_tables()
    yield
    await _truncate_test_tables()
