from typing import Protocol

from app.messaging.inbound_message import Attachment


class MessagingFrontend(Protocol):
    def provider(self) -> str: ...

    def enabled(self) -> bool: ...

    def message_limit(self) -> int: ...

    async def send(self, conversation_id: str, text: str) -> str: ...

    async def edit(self, conversation_id: str, message_id: str, text: str) -> None: ...

    async def download(self, attachment: Attachment) -> bytes: ...


class FrontendUnavailableError(RuntimeError):
    pass


class FrontendRegistry:
    def __init__(self, frontends: list[MessagingFrontend]) -> None:
        self._frontends = {f.provider(): f for f in frontends}

    def find(self, provider: str) -> MessagingFrontend | None:
        frontend = self._frontends.get(provider)
        if frontend is not None and frontend.enabled():
            return frontend
        return None

    def require(self, provider: str) -> MessagingFrontend:
        frontend = self.find(provider)
        if frontend is None:
            raise FrontendUnavailableError(f"Messaging frontend is unavailable: {provider}")
        return frontend
