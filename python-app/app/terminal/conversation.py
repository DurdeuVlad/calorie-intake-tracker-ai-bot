"""Sends a synthetic text update through the normal durable inbox/outbox path,
using the "terminal" provider -- reuses the exact same pipeline real Telegram
traffic goes through (MessagingIngressService/MessagingInboxWorker/
MessagingDispatcher equivalents), just with TerminalFrontend standing in for
the real transport. Ported from TerminalConversation.java."""

import asyncio
import itertools
import time
from dataclasses import dataclass

from app.config import Settings
from app.db.base import session_scope
from app.messaging import ingress, outbox_dispatcher
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging.inbound_message import InboundMessage
from app.messaging.inbox_worker import InboxWorkerDeps
from app.messaging import inbox_worker as inbox_worker_module
from app.terminal.terminal_frontend import TerminalFrontend
from app.terminal.trace_collector import Trace, TerminalTraceCollector

REPLY_TIMEOUT_SECONDS = 45


@dataclass(frozen=True)
class Result:
    reply: str
    trace: Trace | None


class TerminalConversation:
    def __init__(
        self,
        settings: Settings,
        deps: InboxWorkerDeps,
        outbox_registry: FrontendRegistry,
        terminal_frontend: TerminalFrontend,
        traces: TerminalTraceCollector,
        terminal_user_id: int,
        display_name: str,
    ) -> None:
        if str(terminal_user_id) not in settings.allowed_telegram_user_id_set:
            raise ValueError("food-journal.terminal.user-id must be present in ALLOWED_TELEGRAM_USER_IDS")
        self._deps = deps
        self._outbox_registry = outbox_registry
        self._frontend = terminal_frontend
        self._traces = traces
        self._user_id = str(terminal_user_id)
        self._display_name = display_name
        self._event_ids = itertools.count(int(time.time() * 1_000_000))

    async def send(self, text: str) -> Result:
        self._frontend.reset()
        event_id = str(next(self._event_ids))
        message = InboundMessage(
            provider="terminal", event_id=event_id, user_id=self._user_id, conversation_id=self._user_id,
            display_name=self._display_name, language_code=None, text=text, caption=None,
        )
        async with session_scope() as session:
            await ingress.accept(session, message)

        deadline = asyncio.get_event_loop().time() + REPLY_TIMEOUT_SECONDS
        reply: str | None = None
        while reply is None and asyncio.get_event_loop().time() < deadline:
            await inbox_worker_module.process_one(self._deps)
            await outbox_dispatcher.dispatch_batch(self._outbox_registry)
            reply = await self._frontend.await_reply(0.1)

        if reply is None:
            raise TimeoutError(f"No terminal reply arrived within {REPLY_TIMEOUT_SECONDS} seconds")
        return Result(reply, self._traces.await_trace())
