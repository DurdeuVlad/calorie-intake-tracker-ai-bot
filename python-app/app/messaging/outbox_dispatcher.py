import asyncio
import logging

from app.config import get_settings
from app.db.base import session_scope
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging import outbox
from app.repositories import messaging_outbox_repo

logger = logging.getLogger(__name__)


async def dispatch_batch(registry: FrontendRegistry, limit: int = 10) -> int:
    async with session_scope() as session:
        rows = await messaging_outbox_repo.lock_ready(session, limit=limit)
        if not rows:
            await session.rollback()
            return 0
        for row in rows:
            row.claim()
        await session.flush()
        for row in rows:
            try:
                frontend = registry.require(row.provider)
                text = outbox.fit(row.text, frontend.message_limit())
                await frontend.send(row.conversation_id, text)
                row.sent()
            except Exception:
                logger.exception("Failed to send outbound message id=%s", row.id)
                row.retry()
        await session.commit()
        return len(rows)


async def run_forever(registry: FrontendRegistry, stop_event: asyncio.Event) -> None:
    settings = get_settings()
    delay = settings.food_journal_outbox_delay_ms / 1000
    while not stop_event.is_set():
        outbox.begin_dispatch_cycle()
        try:
            processed = await dispatch_batch(registry)
        except Exception:
            logger.exception("Outbox dispatcher tick failed")
            processed = 0
        if not processed:
            await outbox.wait_for_dispatch(delay)
