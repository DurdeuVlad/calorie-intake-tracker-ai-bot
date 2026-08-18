"""Mattermost REST transport, ported from MattermostFrontend.java. Inbound
posts are fed by mattermost_websocket_listener.py."""

import httpx

from app.config import Settings
from app.domain.media_exceptions import MediaProcessingCategory, MediaProcessingException
from app.messaging.inbound_message import Attachment, AttachmentKind

MESSAGE_LIMIT = 16000


class MattermostFrontend:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http or httpx.AsyncClient(
            base_url=settings.mattermost_internal_url or "http://localhost",
            headers={"Authorization": f"Bearer {settings.mattermost_bot_token}"},
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0),
        )

    def provider(self) -> str:
        return "mattermost"

    def enabled(self) -> bool:
        return bool(self._settings.mattermost_internal_url and self._settings.mattermost_bot_token and self._settings.mattermost_bot_user_id)

    def message_limit(self) -> int:
        return MESSAGE_LIMIT

    async def send(self, conversation_id: str, text: str) -> str:
        response = await self._http.post("/api/v4/posts", json={"channel_id": conversation_id, "message": text})
        response.raise_for_status()
        post_id = response.json().get("id")
        if post_id is None:
            raise RuntimeError("Mattermost delivery failed")
        return str(post_id)

    async def edit(self, conversation_id: str, message_id: str, text: str) -> None:
        response = await self._http.put(f"/api/v4/posts/{message_id}", json={"id": message_id, "channel_id": conversation_id, "message": text})
        response.raise_for_status()

    async def download(self, attachment: Attachment) -> bytes:
        try:
            response = await self._http.get(f"/api/v4/files/{attachment.handle}")
            response.raise_for_status()
            if not response.content:
                raise RuntimeError("media unavailable")
            return response.content
        except Exception as failure:  # noqa: BLE001
            raise MediaProcessingException(MediaProcessingCategory.TELEGRAM_DOWNLOAD, "Messaging media download failed", failure) from failure

    async def attachment(self, file_id: str) -> Attachment:
        response = await self._http.get(f"/api/v4/files/{file_id}/info")
        response.raise_for_status()
        info = response.json()
        mime = info.get("mime_type") or "application/octet-stream"
        name = info.get("name")
        if mime.startswith("image/"):
            kind = AttachmentKind.PHOTO
        elif mime.startswith("audio/"):
            kind = AttachmentKind.VOICE
        else:
            kind = AttachmentKind.DOCUMENT
        return Attachment(kind, file_id, mime, name)

    async def direct_channel(self, user_id: str) -> str:
        response = await self._http.post("/api/v4/channels/direct", json=[self._settings.mattermost_bot_user_id, user_id])
        response.raise_for_status()
        channel_id = response.json().get("id")
        if channel_id is None:
            raise RuntimeError("Mattermost direct channel failed")
        return str(channel_id)

    async def close(self) -> None:
        await self._http.aclose()
