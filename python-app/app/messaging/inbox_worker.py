import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import select

from app.config import Settings, get_settings
from app.db.base import session_scope
from app.db.models.users import FoodUser
from app.domain.media_exceptions import MediaProcessingCategory, MediaProcessingException
from app.integrations.openai_transcription import OpenAiVoiceTranscriber
from app.integrations.openai_vision import FoodMediaType, OpenAiFoodMediaExtractor
from app.messaging import execution_context, ingress, outbox
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging.inbound_message import AttachmentKind, InboundMessage
from app.repositories import messaging_identity_repo
from app.repositories import telegram_access_repo
from app.repositories.food_user_repo import get_or_create_by_telegram_user_id
from app.repositories.messaging_inbox_repo import lock_ready
from app.services import message_link_service, messaging_daily_status_service
from app.services import telegram_admin_service
from app.services.conversation_memory_service import record_turn
from app.services.journal_application_service import JournalApplicationService

logger = logging.getLogger(__name__)


@dataclass
class InboxWorkerDeps:
    journal: JournalApplicationService
    frontends: FrontendRegistry
    voice: OpenAiVoiceTranscriber | None = None
    media: OpenAiFoodMediaExtractor | None = None


async def allowed(session, message: InboundMessage, settings: Settings) -> bool:
    if message.provider == "telegram":
        if not settings.telegram_frontend_enabled:
            return False
        await telegram_access_repo.seed_bootstrap_grants(session, settings)
        return await telegram_access_repo.allowed(session, int(message.user_id))
    if message.provider == "mattermost":
        return settings.mattermost_enabled and message.user_id in settings.allowed_mattermost_user_id_set
    if message.provider == "terminal":
        return True
    return False


async def _load_user_by_id(session, user_id: int) -> FoodUser:
    return (await session.execute(select(FoodUser).where(FoodUser.id == user_id))).scalar_one()


async def resolve_identity_user(session, message: InboundMessage, default_timezone: str) -> FoodUser | None:
    """Resolves the FoodUser for this inbound message's identity, creating a new
    FoodUser + MessagingIdentity on first contact for self-service providers
    (telegram, terminal). Unlike the Java predecessor, this never calls back
    into the command/agent handler to bootstrap the account -- it creates the
    row directly -- so there is no call site here that could accidentally
    double-record conversation memory for an internal system-triggered turn."""
    identity = await messaging_identity_repo.find_by_provider_and_external_id(session, message.provider, message.user_id)
    if identity is not None:
        return await _load_user_by_id(session, identity.user_id)
    if message.provider not in ("telegram", "terminal"):
        return None  # other providers must link via /link first
    user = await get_or_create_by_telegram_user_id(session, int(message.user_id), message.display_name, default_timezone)
    await messaging_identity_repo.create(session, user, message.provider, message.user_id)
    return user


async def _extract_media_text(deps: InboxWorkerDeps, message: InboundMessage) -> str:
    attachment = message.attachments[0]
    frontend = deps.frontends.require(message.provider)
    data = await frontend.download(attachment)
    if attachment.kind == AttachmentKind.VOICE:
        if deps.voice is None:
            raise MediaProcessingException(MediaProcessingCategory.NOT_CONFIGURED, "Voice transcription is not configured")
        return await deps.voice.transcribe(data, attachment.mime_type)
    media_type = FoodMediaType.PHOTO if attachment.kind == AttachmentKind.PHOTO else FoodMediaType.DOCUMENT
    if deps.media is None:
        raise MediaProcessingException(MediaProcessingCategory.NOT_CONFIGURED, "Media extraction is not configured")
    return await deps.media.extract(data, attachment.mime_type, media_type)


async def handle_message(session, message: InboundMessage, settings: Settings, deps: InboxWorkerDeps) -> None:
    if not await allowed(session, message, settings):
        logger.warning("Dropping message from disallowed sender: provider=%s user_id=%s", message.provider, message.user_id)
        return

    text = (message.text or "").strip()
    caption = (message.caption or "").strip()

    if message.provider == "telegram":
        admin_response = await telegram_admin_service.handle_command(
            session,
            text,
            int(message.user_id),
            message.conversation_id == message.user_id,
        )
        if admin_response is not None:
            await outbox.reply(session, message.provider, message.conversation_id, admin_response)
            return

    if message.provider == "telegram" and text.lower() == "/link":
        user = await resolve_identity_user(session, message, deps.journal.default_timezone)
        code = await message_link_service.issue(session, user)
        await outbox.reply(
            session, message.provider, message.conversation_id,
            f"Your Mattermost link code is {code}. Send `link CODE` in a direct message to the Mattermost bot within 10 minutes.",
        )
        return
    if message.provider == "mattermost" and text.lower().startswith("link "):
        try:
            await message_link_service.redeem(session, text[5:].strip().upper(), message.provider, message.user_id, message.conversation_id)
            await outbox.reply(session, message.provider, message.conversation_id, "Your existing food journal is linked.")
        except message_link_service.LinkError:
            await outbox.reply(session, message.provider, message.conversation_id, "That link code is invalid, expired, or already used.")
        return

    if message.attachments and not text:
        try:
            text = await _extract_media_text(deps, message)
        except Exception:
            logger.error(
                "Media processing failed: provider=%s kind=%s", message.provider, message.attachments[0].kind, exc_info=True
            )
            await outbox.reply(session, message.provider, message.conversation_id, "I could not analyze that media. Please send clearer media or text.")
            return

    if caption:
        text = f"{text}\nUser caption: {caption}" if text else caption
    if not text:
        return

    user = await resolve_identity_user(session, message, deps.journal.default_timezone)
    if user is None:
        return
    await messaging_identity_repo.ensure_route(session, user, message.provider, message.conversation_id)

    final_text = text

    async def _run_journal() -> str:
        return await deps.journal.handle(session, user, message.conversation_id, final_text)

    response = await execution_context.run(_run_journal)
    await record_turn(session, user, text, response)
    await messaging_daily_status_service.refresh(session, user, message.provider, message.conversation_id)
    await outbox.reply(session, message.provider, message.conversation_id, response)


async def process_one(deps: InboxWorkerDeps | None = None) -> bool:
    settings = get_settings()
    if deps is None:
        deps = InboxWorkerDeps(journal=JournalApplicationService(settings.default_timezone), frontends=FrontendRegistry([]))
    async with session_scope() as session:
        row = await lock_ready(session)
        if row is None:
            await session.rollback()
            return False
        row.claim()
        await session.flush()
        try:
            message = ingress.deserialize(row.payload)
            await handle_message(session, message, settings, deps)
            row.complete(row.lease_token)
        except Exception:
            logger.exception("Failed to process messaging inbox row id=%s", row.id)
            row.retry(row.lease_token)
        await session.commit()
    return True


async def run_forever(stop_event: asyncio.Event, deps: InboxWorkerDeps | None = None) -> None:
    settings = get_settings()
    delay = settings.food_journal_inbox_delay_ms / 1000
    while not stop_event.is_set():
        try:
            processed = await process_one(deps)
        except Exception:
            logger.exception("Inbox worker tick failed")
            processed = False
        if not processed:
            await asyncio.sleep(delay)
