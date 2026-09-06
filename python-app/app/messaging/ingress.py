import json
import logging
import re
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.constraints import (
    MAX_ATTACHMENT_COUNT,
    MAX_ATTACHMENT_HANDLE_CHARS,
    MAX_BIGINT,
    MAX_EVENT_ID_CHARS,
    MAX_FILE_NAME_CHARS,
    MAX_IDENTIFIER_CHARS,
    MAX_INBOX_PAYLOAD_CHARS,
    MAX_MESSAGE_CHARS,
    MAX_MIME_TYPE_CHARS,
    MAX_PROVIDER_CHARS,
    MAX_TEXT_CHARS,
)
from app.db.models.messaging import MessagingInboxMessage
from app.messaging.inbound_message import Attachment, AttachmentKind, InboundMessage

logger = logging.getLogger(__name__)
_ALLOWED_PROVIDERS = frozenset({"telegram", "mattermost", "terminal"})
_MAX_SIGNED_ID = MAX_BIGINT
_MAX_PAYLOAD_CHARS = MAX_INBOX_PAYLOAD_CHARS
_MAX_EVENT_ID_CHARS = MAX_EVENT_ID_CHARS
_MAX_EXTERNAL_ID_CHARS = MAX_IDENTIFIER_CHARS
_MAX_DISPLAY_NAME_CHARS = MAX_TEXT_CHARS
_MAX_LANGUAGE_CODE_CHARS = MAX_PROVIDER_CHARS
_MAX_MESSAGE_CHARS = MAX_MESSAGE_CHARS
_MAX_ATTACHMENT_COUNT = MAX_ATTACHMENT_COUNT
_MAX_ATTACHMENT_HANDLE_CHARS = MAX_ATTACHMENT_HANDLE_CHARS
_MAX_MIME_TYPE_CHARS = MAX_MIME_TYPE_CHARS
_MAX_FILE_NAME_CHARS = MAX_FILE_NAME_CHARS
_MISSING = object()
_NUMERIC_ID_RE = re.compile(r"^-?\d+$")


class InboundPayloadError(ValueError):
    """Raised when a persisted inbox payload cannot be deserialized safely."""


def _compat_value(data: dict, *keys: str) -> object:
    """Read current and legacy field names without accepting ambiguity."""
    values = [data[key] for key in keys if key in data]
    if not values:
        return _MISSING
    first = values[0]
    if any(value != first for value in values[1:]):
        raise ValueError(f"conflicting values for {keys[0]}")
    return first


def _validate_text(value: str, key: str, limit: int, *, allow_newlines: bool = False) -> str:
    if len(value) > limit:
        raise ValueError(f"{key} is too long")
    allowed_controls = "\r\n\t" if allow_newlines else ""
    if any(ord(char) < 32 and char not in allowed_controls for char in value):
        raise ValueError(f"{key} contains unsupported control characters")
    if any(ord(char) == 127 for char in value):
        raise ValueError(f"{key} contains unsupported control characters")
    return value


def _required_text(data: dict, key: str, *legacy_keys: str, limit: int = _MAX_EVENT_ID_CHARS) -> str:
    value = _compat_value(data, key, *legacy_keys)
    if value is _MISSING or not isinstance(value, str) or not value:
        raise TypeError(f"{key} must be a non-empty string")
    return _validate_text(value, key, limit)


def _optional_text(
    data: dict,
    key: str,
    *legacy_keys: str,
    limit: int = _MAX_MESSAGE_CHARS,
    allow_newlines: bool = True,
) -> str | None:
    value = _compat_value(data, key, *legacy_keys)
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string or null")
    return _validate_text(value, key, limit, allow_newlines=allow_newlines)


def _validate_provider_identifiers(provider: str, user_id: str, conversation_id: str) -> None:
    if provider not in {"telegram", "terminal"}:
        return

    if not _NUMERIC_ID_RE.fullmatch(user_id):
        raise ValueError("user_id must be a numeric identifier")
    parsed_user_id = int(user_id)
    if not 1 <= parsed_user_id <= _MAX_SIGNED_ID:
        raise ValueError("user_id is outside the supported range")

    if not _NUMERIC_ID_RE.fullmatch(conversation_id):
        raise ValueError("conversation_id must be a numeric identifier")
    parsed_conversation_id = int(conversation_id)
    minimum_conversation_id = 1 if provider == "terminal" else -(_MAX_SIGNED_ID + 1)
    if not minimum_conversation_id <= parsed_conversation_id <= _MAX_SIGNED_ID:
        raise ValueError("conversation_id is outside the supported range")


def _deserialize_attachment(raw: object) -> Attachment:
    if not isinstance(raw, dict):
        raise TypeError("attachments must contain objects")
    try:
        kind = AttachmentKind(_compat_value(raw, "kind"))
    except (TypeError, ValueError) as failure:
        raise TypeError("attachment kind is invalid") from failure
    handle = _required_text(raw, "handle", limit=_MAX_ATTACHMENT_HANDLE_CHARS)
    mime_type = _optional_text(raw, "mime_type", "mimeType", limit=_MAX_MIME_TYPE_CHARS, allow_newlines=False)
    file_name = _optional_text(
        raw, "file_name", "fileName", "name", limit=_MAX_FILE_NAME_CHARS, allow_newlines=False
    )
    return Attachment(kind=kind, handle=handle, mime_type=mime_type, file_name=file_name)


def _required_value(value: object, key: str, limit: int) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{key} must be a non-empty string")
    return _validate_text(value, key, limit)


def _optional_value(value: object, key: str, limit: int, *, allow_newlines: bool = True) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string or null")
    return _validate_text(value, key, limit, allow_newlines=allow_newlines)


def _validate_inbound_message(message: InboundMessage) -> None:
    """Validate the live ingress object before it can reach durable storage."""
    if not isinstance(message, InboundMessage):
        raise TypeError("inbound message must have the supported message shape")

    provider = _required_value(message.provider, "provider", MAX_PROVIDER_CHARS)
    if provider not in _ALLOWED_PROVIDERS:
        raise ValueError("provider is invalid")
    user_id = _required_value(message.user_id, "user_id", _MAX_EXTERNAL_ID_CHARS)
    conversation_id = _required_value(message.conversation_id, "conversation_id", _MAX_EXTERNAL_ID_CHARS)
    _required_value(message.event_id, "event_id", _MAX_EVENT_ID_CHARS)
    _validate_provider_identifiers(provider, user_id, conversation_id)
    _optional_value(message.display_name, "display_name", _MAX_DISPLAY_NAME_CHARS, allow_newlines=False)
    _optional_value(message.language_code, "language_code", _MAX_LANGUAGE_CODE_CHARS, allow_newlines=False)
    _optional_value(message.text, "text", _MAX_MESSAGE_CHARS)
    _optional_value(message.caption, "caption", _MAX_MESSAGE_CHARS)

    if not isinstance(message.attachments, list) or len(message.attachments) > _MAX_ATTACHMENT_COUNT:
        raise ValueError("attachments are invalid")
    for attachment in message.attachments:
        if not isinstance(attachment, Attachment) or not isinstance(attachment.kind, AttachmentKind):
            raise TypeError("attachment is invalid")
        _required_value(attachment.handle, "handle", _MAX_ATTACHMENT_HANDLE_CHARS)
        _optional_value(attachment.mime_type, "mime_type", _MAX_MIME_TYPE_CHARS, allow_newlines=False)
        _optional_value(attachment.file_name, "file_name", _MAX_FILE_NAME_CHARS, allow_newlines=False)


def _serialize(message: InboundMessage) -> str:
    try:
        _validate_inbound_message(message)
        payload = asdict(message)
        payload["attachments"] = [
            {"kind": a["kind"].value, **{k: v for k, v in a.items() if k != "kind"}}
            for a in payload["attachments"]
        ]
        serialized = json.dumps(payload)
        if len(serialized) > _MAX_PAYLOAD_CHARS:
            raise ValueError("inbox payload is too large")
        return serialized
    except (TypeError, ValueError) as failure:
        raise InboundPayloadError("The inbound message is invalid.") from failure


def deserialize(payload: str) -> InboundMessage:
    try:
        if not isinstance(payload, str) or len(payload) > _MAX_PAYLOAD_CHARS:
            raise ValueError("inbox payload is too large")
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise TypeError("inbox payload must be an object")
        provider = _required_text(data, "provider", limit=MAX_PROVIDER_CHARS)
        if provider not in _ALLOWED_PROVIDERS:
            raise ValueError("provider is invalid")
        event_id = _required_text(data, "event_id", "eventId", limit=_MAX_EVENT_ID_CHARS)
        user_id = _required_text(data, "user_id", "userId", limit=_MAX_EXTERNAL_ID_CHARS)
        conversation_id = _required_text(data, "conversation_id", "conversationId", limit=_MAX_EXTERNAL_ID_CHARS)
        _validate_provider_identifiers(provider, user_id, conversation_id)
        raw_attachments = _compat_value(data, "attachments")
        if raw_attachments is _MISSING:
            raw_attachments = []
        if not isinstance(raw_attachments, list) or len(raw_attachments) > _MAX_ATTACHMENT_COUNT:
            raise ValueError("attachments are invalid")
        message = InboundMessage(
            provider=provider,
            event_id=event_id,
            user_id=user_id,
            conversation_id=conversation_id,
            display_name=_optional_text(
                data, "display_name", "displayName", limit=_MAX_DISPLAY_NAME_CHARS, allow_newlines=False
            ),
            language_code=_optional_text(
                data, "language_code", "languageCode", limit=_MAX_LANGUAGE_CODE_CHARS, allow_newlines=False
            ),
            text=_optional_text(data, "text", limit=_MAX_MESSAGE_CHARS),
            caption=_optional_text(data, "caption", limit=_MAX_MESSAGE_CHARS),
            attachments=[_deserialize_attachment(raw) for raw in raw_attachments],
        )
        _validate_inbound_message(message)
        return message
    except (KeyError, RecursionError, TypeError, ValueError) as failure:
        raise InboundPayloadError("The persisted inbox payload is invalid.") from failure


async def accept(session: AsyncSession, message: InboundMessage) -> bool:
    """Idempotent on (provider, event_id) -- at-least-once provider delivery
    (e.g. Telegram retrying its webhook call) must not create duplicate rows.

    Validation happens before the row is added so hostile or malformed live
    frontend data cannot be used to persist an oversized inbox payload that the
    worker would only reject later.
    """
    try:
        payload = _serialize(message)
    except InboundPayloadError:
        logger.warning("Rejected invalid inbound message before persistence")
        return False

    received_at = datetime.now(UTC)
    row = MessagingInboxMessage(
        provider=message.provider,
        event_id=message.event_id,
        payload=payload,
        received_at=received_at,
        next_attempt_at=received_at,
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
