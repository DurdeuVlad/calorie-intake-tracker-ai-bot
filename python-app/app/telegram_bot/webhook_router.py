import hmac
import logging
from aiogram.types import Update
from fastapi import APIRouter, Header, Request, Response

from app.config import get_settings
from app.db.base import session_scope
from app.messaging import ingress
from app.messaging.inbound_message import Attachment, AttachmentKind, InboundMessage

logger = logging.getLogger(__name__)
router = APIRouter()


def _valid_secret(secret: str | None) -> bool:
    settings = get_settings()
    if secret is None or not settings.telegram_webhook_secret:
        return False
    return hmac.compare_digest(secret.encode("utf-8"), settings.telegram_webhook_secret.encode("utf-8"))


def _to_inbound_message(update: Update) -> InboundMessage | None:
    message = update.message
    if message is None or message.from_user is None or message.chat is None:
        return None

    attachments: list[Attachment] = []
    if message.voice is not None:
        attachments.append(Attachment(AttachmentKind.VOICE, message.voice.file_id, message.voice.mime_type))
    if message.photo:
        largest = message.photo[-1]
        attachments.append(Attachment(AttachmentKind.PHOTO, largest.file_id, "image/jpeg"))
    if message.document is not None:
        attachments.append(
            Attachment(
                AttachmentKind.DOCUMENT, message.document.file_id, message.document.mime_type, message.document.file_name
            )
        )

    return InboundMessage(
        provider="telegram",
        event_id=str(update.update_id),
        user_id=str(message.from_user.id),
        conversation_id=str(message.chat.id),
        display_name=message.from_user.first_name,
        language_code=message.from_user.language_code,
        text=message.text,
        caption=message.caption,
        attachments=attachments,
    )


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    if not _valid_secret(x_telegram_bot_api_secret_token):
        return Response(status_code=403)

    body = await request.json()
    try:
        update = Update.model_validate(body)
    except Exception:
        logger.warning("Rejected malformed Telegram update payload")
        return Response(status_code=200)

    inbound = _to_inbound_message(update)
    if inbound is None:
        return Response(status_code=200)

    async with session_scope() as session:
        accepted = await ingress.accept(session, inbound)
    logger.info("Telegram webhook handled: event_id=%s accepted=%s", update.update_id, accepted)

    return Response(status_code=200)
