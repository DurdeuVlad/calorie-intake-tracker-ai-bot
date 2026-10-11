"""Synchronous journal turns for the mobile API.

This is the inbox worker's message path minus the store-and-forward steps:
media never reaches a messaging Attachment/frontend download (the endpoint
transcribes in-request), the reply returns in the HTTP response instead of
going through messaging_outbox, and no messaging_routes/messaging_daily_status
rows are written -- there is no 'mobile' MessagingFrontend, so those rows
would sit dirty while the dispatchers fail on them every tick.

What is deliberately kept identical to the worker path: the same agent wiring
(build_journal_application_service), JournalApplicationService.handle for
language/settings/command behavior, execution_context.run so the tool
executor's pinned-status refresh stays suppressed, and record_turn so mobile
messages join the same 10-turn conversation memory.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.builder import build_journal_application_service
from app.agent.trace_sink import NoopTraceSink
from app.config import get_settings
from app.db.models.users import FoodUser
from app.domain.agent_types import AgentToolResult, ToolCall
from app.integrations.openai_transcription import OpenAiVoiceTranscriber
from app.messaging import execution_context
from app.services.conversation_memory_service import record_turn
from app.services.journal_application_service import JournalApplicationService


@dataclass
class MobileJournalDeps:
    journal: JournalApplicationService
    voice: OpenAiVoiceTranscriber | None = None


@dataclass(frozen=True)
class JournalTurnResult:
    reply: str
    actions: list[dict[str, Any]] = field(default_factory=list)


class _AppliedActionsCapture(NoopTraceSink):
    """Collects the per-action results of the apply_journal_actions tool so the
    client can render the editable confirmation card (audit section 4.3). The
    agent short-circuits to its canonical reply after the first successful
    apply, so the last ok result is the relevant one."""

    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []

    def tool_result(self, call: ToolCall, result: AgentToolResult) -> None:
        if call.name == "apply_journal_actions" and result.ok:
            self.results = list(result.data.get("results") or [])


_deps: MobileJournalDeps | None = None


def get_message_deps() -> MobileJournalDeps:
    """Process-lifetime deps, built once like run.py builds the worker deps --
    the journal service holds shared httpx clients that must not be recreated
    per request. Tests substitute this via FastAPI dependency_overrides."""
    global _deps
    if _deps is None:
        settings = get_settings()
        _deps = MobileJournalDeps(
            journal=build_journal_application_service(settings),
            voice=OpenAiVoiceTranscriber(settings),
        )
    return _deps


async def run_turn(
    session: AsyncSession,
    user: FoodUser,
    chat_id: str,
    text: str,
    deps: MobileJournalDeps,
) -> JournalTurnResult:
    capture = _AppliedActionsCapture()

    async def _invoke() -> str:
        return await deps.journal.handle(session, user, chat_id, text, trace=capture)

    reply = await execution_context.run(_invoke)
    await record_turn(session, user, text, reply)
    return JournalTurnResult(reply=reply, actions=capture.results)
