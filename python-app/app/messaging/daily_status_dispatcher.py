"""Provider-neutral daily-status text dispatch, ported from
MessagingDailyStatusDispatcher.java. Errors are only logged (row stays dirty
and retries on the next tick -- no lease/backoff bookkeeping here, matching
the Java predecessor exactly)."""

import asyncio
import logging

from app.config import get_settings
from app.db.base import session_scope
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging.outbox import fit
from app.repositories import messaging_daily_status_repo

logger = logging.getLogger(__name__)


async def dispatch_once(registry: FrontendRegistry) -> bool:
    async with session_scope() as session:
        status = await messaging_daily_status_repo.lock_dirty(session)
        if status is None:
            await session.rollback()
            return False
        try:
            frontend = registry.require(status.provider)
            text = fit(status.text, frontend.message_limit())
            if status.remote_message_id is None:
                message_id = await frontend.send(status.conversation_id, text)
                status.delivered(message_id)
            else:
                await frontend.edit(status.conversation_id, status.remote_message_id, text)
                status.delivered(status.remote_message_id)
        except Exception as failure:  # noqa: BLE001
            logger.error("Failed to dispatch daily status: %s", failure)
        await session.commit()
    return True


async def run_forever(registry: FrontendRegistry, stop_event: asyncio.Event) -> None:
    settings = get_settings()
    delay = settings.food_journal_outbox_delay_ms / 1000
    while not stop_event.is_set():
        try:
            processed = await dispatch_once(registry)
        except Exception:
            logger.exception("Daily status dispatcher tick failed")
            processed = False
        if not processed:
            await asyncio.sleep(delay)
