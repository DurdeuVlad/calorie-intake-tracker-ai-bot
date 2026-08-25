"""Local stand-in transport for the "terminal" provider; captures replies
in-process instead of calling a real API. Terminal usage is single-threaded
and sequential (one send() awaited at a time), so a simple FIFO queue is
sufficient -- no correlation id needed between a send and its reply."""

import asyncio

from app.messaging.inbound_message import Attachment


class TerminalFrontend:
    def __init__(self) -> None:
        self._deliveries: asyncio.Queue[str] = asyncio.Queue()

    def provider(self) -> str:
        return "terminal"

    def enabled(self) -> bool:
        return True

    def message_limit(self) -> int:
        return 4096

    async def send(self, conversation_id: str, text: str) -> str:
        await self._deliveries.put(text)
        return "0"

    async def edit(self, conversation_id: str, message_id: str, text: str) -> None:
        await self._deliveries.put(text)

    async def download(self, attachment: Attachment) -> bytes:
        raise NotImplementedError("Terminal mode does not support media attachments")

    async def await_reply(self, timeout: float) -> str | None:
        try:
            return await asyncio.wait_for(self._deliveries.get(), timeout=timeout)
        except TimeoutError:
            return None

    def reset(self) -> None:
        while not self._deliveries.empty():
            self._deliveries.get_nowait()
