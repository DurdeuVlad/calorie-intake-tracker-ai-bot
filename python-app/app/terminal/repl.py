"""Terminal chat/eval entrypoint, ported from TerminalChatRunner.java.
Run interactively with `python -m app.terminal.repl`, or set TERMINAL_EVAL_FILE
to run the fixture-driven evaluation instead. Never used by the production
server -- it is a standalone dev/eval tool against a dev database."""

import asyncio
import sys

from app.agent.builder import build_journal_application_service
from app.config import Settings, TerminalSettings, get_settings, get_terminal_settings
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging.inbox_worker import InboxWorkerDeps
from app.terminal import eval_runner
from app.terminal.conversation import TerminalConversation
from app.terminal.terminal_frontend import TerminalFrontend
from app.terminal.trace_collector import TerminalTraceCollector


def build_conversation(traces: TerminalTraceCollector) -> tuple[TerminalConversation, Settings, TerminalSettings]:
    settings = get_settings()
    terminal = get_terminal_settings()
    journal = build_journal_application_service(settings, trace=traces)
    terminal_frontend = TerminalFrontend()
    registry = FrontendRegistry([terminal_frontend])
    deps = InboxWorkerDeps(journal=journal, frontends=registry)
    chat = TerminalConversation(
        settings, deps, registry, terminal_frontend, traces, terminal.user_id, terminal.display_name
    )
    return chat, settings, terminal


def _print_trace(trace) -> None:
    if trace is None:
        print("trace> no agent call")
        return
    print(f"trace> model turns={trace.model_turns}, tools={trace.tools}")


async def _read_line(prompt: str) -> str | None:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, input, prompt)
    except EOFError:
        return None


async def _repl(chat: TerminalConversation) -> None:
    print("Food Journal terminal chat. Type :help for commands.")
    trace_enabled = False
    while True:
        line = await _read_line("you> ")
        if line is None or line.strip().lower() == ":quit":
            break
        command = line.strip()
        if command.lower() == ":help":
            print(":help, :trace on, :trace off, :quit. Any other text is sent as a Telegram-style message.")
            continue
        if command.lower() == ":trace on":
            trace_enabled = True
            print("Trace enabled.")
            continue
        if command.lower() == ":trace off":
            trace_enabled = False
            print("Trace disabled.")
            continue
        if not line.strip():
            continue
        try:
            result = await chat.send(line)
            print(f"bot> {result.reply}")
            if trace_enabled:
                _print_trace(result.trace)
        except Exception as failure:
            print(f"bot> Local processing failed: {type(failure).__name__}")


async def main() -> int:
    traces = TerminalTraceCollector()
    chat, settings, terminal = build_conversation(traces)
    if terminal.eval_file:
        return await eval_runner.run(terminal.eval_file, chat, settings, terminal)
    await _repl(chat)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
