"""Telegram-only pinned "today's total" message with durable retry recovery."""

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
                except Exception:  # noqa: BLE001
                    logger.warning("Pinned-status edit failed; sending a replacement (status_id=%s)", status.id)
                    old_message_id = message_id
                    message_id = int(await telegram.send(str(status.chat_id), status.text))
                    await daily_status_service.remember_message(session, status.id, status.lease_token, message_id)
                    try:
                        await telegram.unpin(str(status.chat_id), str(old_message_id))
                    except Exception:  # noqa: BLE001
                        # The replaced message may still be pinned, which would leave
                        # a stale pin outranking the fresh one (Telegram surfaces the
                        # pinned message with the latest send date, not the latest
                        # pin action). Not fatal to this delivery: the new message
                        # still gets pinned below, we just log to see it happen.
                        logger.warning(
                            "Pinned-status unpin of replaced message failed (status_id=%s, old_message_id=%s)",
                            status.id, old_message_id,
                        )

            try:
                await telegram.pin(str(status.chat_id), str(message_id))
            except Exception:
                # Treat pinning as part of delivery. The retry is idempotent for
                # Telegram and prevents an unpinned replacement from becoming a
                # silently accepted final state.
                logger.warning("Pinned-status pin failed (status_id=%s)", status.id)
                raise

            await daily_status_service.mark_delivered(session, status.id, status.version, status.lease_token, message_id)
        except Exception:  # noqa: BLE001
            logger.warning("Pinned-status delivery failed; scheduling retry (status_id=%s)")
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
