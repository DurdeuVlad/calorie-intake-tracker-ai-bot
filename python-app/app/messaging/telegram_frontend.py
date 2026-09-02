import logging

import httpx
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.token import TokenValidationError

from app.config import Settings
from app.messaging.inbound_message import Attachment

MESSAGE_LIMIT = 4096

logger = logging.getLogger(__name__)


class TelegramFrontend:
    """Telegram HTTP details live here, outside the journal pipeline."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # aiogram validates the token's shape synchronously in Bot.__init__, unlike
        # httpx-based frontends -- a blank or placeholder TELEGRAM_BOT_TOKEN (e.g. an
        # unconfigured deployment, or a CI/local-dev smoke test) must not crash the
        # whole process at startup. enabled() already reports False in that case, so
        # every other frontend method is unreachable through FrontendRegistry.
        try:
            self._bot: Bot | None = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties())
        except TokenValidationError:
            logger.warning("TELEGRAM_BOT_TOKEN is missing or malformed; the Telegram frontend is disabled")
            self._bot = None
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0))

    def provider(self) -> str:
        return "telegram"

    def enabled(self) -> bool:
        return self._bot is not None and bool(self._settings.telegram_bot_token)

    def message_limit(self) -> int:
        return MESSAGE_LIMIT

    async def send(self, conversation_id: str, text: str) -> str:
        message = await self._bot.send_message(chat_id=int(conversation_id), text=text)
        return str(message.message_id)

    async def send_typing(self, conversation_id: str) -> None:
        """Show immediate, ephemeral progress while a durable inbox job runs."""
        if self._bot is None:
            return
        await self._bot.send_chat_action(chat_id=int(conversation_id), action=ChatAction.TYPING)

    async def edit(self, conversation_id: str, message_id: str, text: str) -> None:
        try:
            await self._bot.edit_message_text(chat_id=int(conversation_id), message_id=int(message_id), text=text)
        except TelegramBadRequest as failure:
            # Telegram rejects an edit whose content exactly matches the message's
            # current content. That is a functional no-op success (the displayed
            # text is already correct), not a delivery failure -- without this,
            # every dispatcher calling edit() logs a spurious ERROR and marks a
            # successful delivery for retry whenever nothing actually changed.
            if "message is not modified" in failure.message.lower():
                logger.info("Telegram edit was a no-op (content unchanged): conversation_id=%s message_id=%s", conversation_id, message_id)
                return
            raise

    async def pin(self, conversation_id: str, message_id: str) -> None:
        await self._bot.pin_chat_message(
            chat_id=int(conversation_id), message_id=int(message_id), disable_notification=True
        )

    async def unpin(self, conversation_id: str, message_id: str) -> None:
        try:
            await self._bot.unpin_chat_message(chat_id=int(conversation_id), message_id=int(message_id))
        except TelegramBadRequest as failure:
            # Already unpinned or the message itself is gone -- both leave the
            # chat in the desired state, so this is not a failure to surface.
            if "message to unpin not found" in failure.message.lower() or "message not found" in failure.message.lower():
                return
            raise

    async def download(self, attachment: Attachment) -> bytes:
        """Downloads via a hand-rolled URL, NOT aiogram's bot.download_file() /
        any URL-templating helper. Telegram's file_path can contain internal `/`
        separators (e.g. "voice/file_123.oga"); a URL-templating helper would
        percent-encode those separators (voice%2Ffile_123.oga), 404ing against
        Telegram's file server. This exact bug already broke every voice/photo
        download once in the Java predecessor of this app -- plain string
        concatenation after stripping one leading slash is the fix, verified
        against the corrected Java implementation."""
        file = await self._bot.get_file(attachment.handle)
        file_path = file.file_path or ""
        raw_path = file_path.removeprefix("/")
        token = self._settings.telegram_bot_token
        url = f"https://api.telegram.org/file/bot{token}/{raw_path}"
        response = await self._http.get(url)
        response.raise_for_status()
        return response.content

    async def close(self) -> None:
        if self._bot is not None:
            await self._bot.session.close()
        await self._http.aclose()
