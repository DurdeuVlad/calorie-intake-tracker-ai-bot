import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.messaging.inbound_message import Attachment, InboundMessage
from app.db.models.messaging import MessagingInboxMessage

logger = logging.getLogger(__name__)


def _serialize(message: InboundMessage) -> str:
    payload = asdict(message)
    payload["attachments"] = [
        {"kind": a["kind"].value if hasattr(a["kind"], "value") else a["kind"], **{k: v for k, v in a.items() if k != "kind"}}
        for a in payload["attachments"]
    ]
    return json.dumps(payload)


def deserialize(payload: str) -> InboundMessage:
    data = json.loads(payload)
    attachments = [Attachment(**a) for a in data.get("attachments", [])]
    return InboundMessage(
        provider=data["provider"],
        event_id=data["event_id"],
        user_id=data["user_id"],
        conversation_id=data["conversation_id"],
        display_name=data.get("display_name"),
        language_code=data.get("language_code"),
        text=data.get("text"),
        caption=data.get("caption"),
        attachments=attachments,
    )


async def accept(session: AsyncSession, message: InboundMessage) -> bool:
    """Idempotent on (provider, event_id) -- at-least-once provider delivery
    (e.g. Telegram retrying its webhook call) must not create duplicate rows."""
    row = MessagingInboxMessage(
        provider=message.provider,
        event_id=message.event_id,
        payload=_serialize(message),
        next_attempt_at=datetime.now(timezone.utc),
    )
    session.add(row)
    try:
        await session.commit()
        logger.info("Inbox accepted: provider=%s event_id=%s", message.provider, message.event_id)
        return True
    except IntegrityError:
        await session.rollback()
        logger.info("Inbox duplicate ignored: provider=%s event_id=%s", message.provider, message.event_id)
        return False
