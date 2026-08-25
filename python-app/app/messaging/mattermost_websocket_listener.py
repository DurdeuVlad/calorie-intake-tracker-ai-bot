"""Maintains the authenticated Mattermost event stream, ported from
MattermostWebSocketListener.java. Reconnects are safe because inbox keys
(provider, event_id) are durable -- a missed/duplicate delivery during a
reconnect window is handled by the normal at-least-once ingress idempotency."""

import asyncio
import json
import logging

import websockets

from app.config import Settings
from app.db.base import session_scope
from app.messaging import ingress
from app.messaging.inbound_message import InboundMessage
from app.messaging.mattermost_frontend import MattermostFrontend

logger = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5


class MattermostWebSocketListener:
    def __init__(self, settings: Settings, frontend: MattermostFrontend) -> None:
        self._settings = settings
        self._frontend = frontend
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="mattermost-websocket-listener")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Mattermost websocket listener task raised during shutdown")

    async def _run(self) -> None:
        url = self._settings.mattermost_internal_url.replace("http", "ws", 1) + "/api/v4/websocket"
        headers = {"Authorization": f"Bearer {self._settings.mattermost_bot_token}"}
        while self._running:
            try:
                async with websockets.connect(url, additional_headers=headers) as socket:
                    async for raw in socket:
                        if not self._running:
                            break
                        await self._handle_frame(raw)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Mattermost websocket connection error, reconnecting in %ss", RECONNECT_DELAY_SECONDS, exc_info=True)
            if self._running:
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    async def _handle_frame(self, raw: str | bytes) -> None:
        try:
            frame = json.loads(raw)
            if frame.get("event") == "posted":
                await self._posted(frame)
        except Exception:
            logger.debug("Ignoring malformed Mattermost websocket frame", exc_info=True)

    async def _posted(self, frame: dict) -> None:
        data = frame.get("data") or {}
        try:
            post = json.loads(data.get("post") or "{}")
        except json.JSONDecodeError:
            return
        user_id = str(post.get("user_id") or "")
        if not user_id or user_id == self._settings.mattermost_bot_user_id or user_id not in self._settings.allowed_mattermost_user_id_set:
            return
        if data.get("channel_type") != "D":
            return

        files = []
        for file_id in post.get("file_ids") or []:
            if file_id:
                files.append(await self._frontend.attachment(file_id))

        event_id = str(post.get("id") or "")
        channel_id = str(post.get("channel_id") or "")
        if not event_id or not channel_id:
            return

        inbound = InboundMessage(
            provider="mattermost", event_id=event_id, user_id=user_id, conversation_id=channel_id,
            display_name=data.get("sender_name") or "Member", language_code=None,
            text=post.get("message"), caption=None, attachments=files,
        )
        async with session_scope() as session:
            await ingress.accept(session, inbound)
