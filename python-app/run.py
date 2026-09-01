"""Container entrypoint. Runs the public app (port 8080), the management app
(MANAGEMENT_PORT, default 8081, never publicly exposed), and the inbox/outbox
background workers as asyncio tasks in one process.
"""

import asyncio
import logging
import subprocess
import sys

import uvicorn

from app.agent.builder import build_journal_application_service
from app.config import get_settings
from app.integrations.openai_transcription import OpenAiVoiceTranscriber
from app.integrations.openai_vision import OpenAiFoodMediaExtractor
from app.main import app as public_app
from app.messaging import (
    daily_status_dispatcher,
    inbox_worker,
    outbox_dispatcher,
    pinned_status_dispatcher,
)
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging.inbox_worker import InboxWorkerDeps
from app.messaging.mattermost_frontend import MattermostFrontend
from app.messaging.mattermost_websocket_listener import MattermostWebSocketListener
from app.messaging.telegram_frontend import TelegramFrontend
from app.scheduling import cleanup_jobs, report_scheduler
from app.web.health import create_management_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()

    public_config = uvicorn.Config(public_app, host="0.0.0.0", port=8080, log_level="info")
    management_config = uvicorn.Config(
        create_management_app(), host="0.0.0.0", port=settings.management_port, log_level="info"
    )
    public_server = uvicorn.Server(public_config)
    management_server = uvicorn.Server(management_config)

    telegram_frontend = TelegramFrontend(settings)
    frontends = [telegram_frontend]
    mattermost_frontend: MattermostFrontend | None = None
    mattermost_listener: MattermostWebSocketListener | None = None
    if settings.mattermost_enabled:
        mattermost_frontend = MattermostFrontend(settings)
        frontends.append(mattermost_frontend)
        mattermost_listener = MattermostWebSocketListener(settings, mattermost_frontend)
        mattermost_listener.start()

    registry = FrontendRegistry(frontends)
    journal = build_journal_application_service(settings)
    voice = OpenAiVoiceTranscriber(settings)
    media = OpenAiFoodMediaExtractor(settings)
    deps = InboxWorkerDeps(journal=journal, frontends=registry, voice=voice, media=media)

    stop_event = asyncio.Event()
    tasks = [
        asyncio.create_task(public_server.serve(), name="public-server"),
        asyncio.create_task(management_server.serve(), name="management-server"),
    ]
    if settings.food_journal_scheduling_enabled:
        tasks.append(asyncio.create_task(inbox_worker.run_forever(stop_event, deps), name="inbox-worker"))
        tasks.append(asyncio.create_task(outbox_dispatcher.run_forever(registry, stop_event), name="outbox-dispatcher"))
        tasks.append(asyncio.create_task(daily_status_dispatcher.run_forever(registry, stop_event), name="daily-status-dispatcher"))
        tasks.append(asyncio.create_task(pinned_status_dispatcher.run_forever(telegram_frontend, stop_event), name="pinned-status-dispatcher"))
        tasks.append(asyncio.create_task(report_scheduler.run_forever(stop_event), name="report-scheduler"))
        tasks.append(asyncio.create_task(cleanup_jobs.run_forever(stop_event), name="cleanup-jobs"))
    else:
        logger.info("FOOD_JOURNAL_SCHEDULING_ENABLED=false: background workers not started")

    try:
        await asyncio.gather(*tasks)
    finally:
        stop_event.set()
        await telegram_frontend.close()
        await voice.close()
        await media.close()
        if mattermost_listener is not None:
            await mattermost_listener.stop()
        if mattermost_frontend is not None:
            await mattermost_frontend.close()


def _migrate_database() -> None:
    """Apply pending Alembic revisions before serving traffic.

    Runs unconditionally on every boot so a merged migration can never be
    skipped regardless of how the container was started (auto-deploy,
    manual redeploy, rollback). Alembic no-ops past revisions already
    applied, so this is safe and cheap to run every time.
    """
    result = subprocess.run(["alembic", "upgrade", "head"], check=False)
    if result.returncode != 0:
        logger.error("Alembic migration failed; refusing to start with a stale schema")
        sys.exit(1)


if __name__ == "__main__":
    _migrate_database()
    asyncio.run(main())
