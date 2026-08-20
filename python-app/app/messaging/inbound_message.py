from dataclasses import dataclass, field
from enum import Enum


class AttachmentKind(str, Enum):
    VOICE = "VOICE"
    PHOTO = "PHOTO"
    DOCUMENT = "DOCUMENT"


@dataclass(frozen=True)
class Attachment:
    kind: AttachmentKind
    handle: str
    mime_type: str | None
    file_name: str | None = None


@dataclass(frozen=True)
class InboundMessage:
    """The only message shape the journal processing pipeline accepts, regardless
    of which provider (telegram/mattermost/terminal) it came from."""

    provider: str
    event_id: str
    user_id: str
    conversation_id: str
    display_name: str | None
    language_code: str | None
    text: str | None
    caption: str | None
    attachments: list[Attachment] = field(default_factory=list)
