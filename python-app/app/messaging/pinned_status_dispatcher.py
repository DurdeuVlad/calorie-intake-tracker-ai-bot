"""Telegram-only pinned "today's total" message, ported from
PinnedDailyStatusDispatcher.java. Deliberately has "give up rather than truly
retry" semantics on failure (see PinnedDailyStatus.retry() in
db/models/messaging.py) -- a persistently broken chat must not loop forever."""

import asyncio
import logging

from app.config import get_settings
from app.db.base import session_scope
from app.messaging.telegram_frontend import TelegramFrontend
from app.services import daily_status_service

logger = logging.getLogger(__name__)


async def dispatch_once(telegram: TelegramFrontend) -> bool:
    async with session_scope() as session:
        status = await daily_status_service.claim(session)
        if status is None:
            await session.rollback()
            return False
        await session.flush()

        try:
            message_id = status.message_id
            if message_id is None:
                message_id = int(await telegram.send(str(status.chat_id), status.text))
                await daily_status_service.remember_message(session, status.id, status.lease_token, message_id)
            else:
                try:
                    await telegram.edit(str(status.chat_id), str(message_id), status.text)
                except Exception as edit_error:  # noqa: BLE001
                    logger.warning("Failed to edit pinned message %s, sending new message: %s", message_id, edit_error)
                    message_id = int(await telegram.send(str(status.chat_id), status.text))
                    await daily_status_service.remember_message(session, status.id, status.lease_token, message_id)

            try:
                await telegram.pin(str(status.chat_id), str(message_id))
            except Exception as pin_error:  # noqa: BLE001
                logger.warning("Failed to pin message %s: %s", message_id, pin_error)

            await daily_status_service.mark_delivered(session, status.id, status.version, status.lease_token, message_id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to dispatch pinned daily status id=%s", status.id)
            await daily_status_service.retry(session, status.id, status.lease_token)

        await session.commit()
    return True


async def run_forever(telegram: TelegramFrontend, stop_event: asyncio.Event) -> None:
    settings = get_settings()
    delay = settings.food_journal_outbox_delay_ms / 1000
    while not stop_event.is_set():
        try:
            processed = await dispatch_once(telegram)
        except Exception:
            logger.exception("Pinned status dispatcher tick failed")
            processed = False
        if not processed:
            await asyncio.sleep(delay)
