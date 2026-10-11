import importlib.util
import socket
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.config import get_settings
from app.db.base import session_scope


def _postgres_reachable() -> bool:
    """Integration tests run against the real Postgres provisioned by
    scripts/setup_test_db.sh. Where that database (or the asyncpg driver) is not
    installed -- e.g. a minimal local checkout -- the suite skips rather than
    failing on connection errors."""
    if importlib.util.find_spec("asyncpg") is None:
        return False
    dsn = urlparse(get_settings().asyncpg_dsn)
    try:
        with socket.create_connection((dsn.hostname or "localhost", dsn.port or 5432), timeout=2):
            return True
    except OSError:
        return False


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    if not _postgres_reachable():
        pytest.skip("Postgres test database is not reachable; run scripts/setup_test_db.sh first")
    async with session_scope() as session:
        await session.execute(
            text(
                "TRUNCATE food_users, auth_accounts, mobile_refresh_tokens, "
                "telegram_access_grants, messaging_inbox, messaging_outbox, "
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
