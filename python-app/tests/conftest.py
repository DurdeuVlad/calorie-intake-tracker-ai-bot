import pytest_asyncio

from app.db.base import dispose_engine


@pytest_asyncio.fixture(autouse=True)
async def _fresh_engine_per_test():
    """pytest-asyncio gives each test function its own event loop by default;
    the module-level cached engine/pool in app.db.base must not survive across
    loops, or asyncpg's connection cleanup fails with 'Event loop is closed'."""
    await dispose_engine()
    yield
    await dispose_engine()
