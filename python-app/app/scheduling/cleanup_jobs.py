"""Periodic purges of expired ephemeral rows: pending nutrition quotes
(30-min TTL) and journal change sets (10-min undo window)."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete

from app.db.base import session_scope
from app.db.models.journal_changes import JournalChangeSet
from app.db.models.nutrition import PendingNutritionQuote

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 300


async def purge_expired() -> None:
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        await session.execute(delete(PendingNutritionQuote).where(PendingNutritionQuote.expires_at < now))
        await session.execute(delete(JournalChangeSet).where(JournalChangeSet.expires_at < now))
        await session.commit()


async def run_forever(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await purge_expired()
        except Exception:
            logger.exception("Cleanup job tick failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CLEANUP_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass
