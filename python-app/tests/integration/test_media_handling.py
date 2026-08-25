"""Attachment handling in the inbox worker: download -> transcribe/extract ->
feed the resulting text through the normal message pipeline, or reply with a
graceful fallback if anything in that chain fails -- mirrors
MessagingInboxWorker.process()'s attachment branch exactly."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import get_settings
from app.db.base import session_scope
from app.db.models.messaging import MessagingOutboundMessage, TelegramAccessGrant
from app.messaging import inbox_worker, ingress
from app.messaging.frontend_registry import FrontendRegistry
from app.messaging.inbound_message import Attachment, AttachmentKind, InboundMessage
from app.messaging.inbox_worker import InboxWorkerDeps
from app.services.journal_application_service import JournalApplicationService


class StubFrontend:
    def __init__(self, payload: bytes = b"fake-bytes", fail: bool = False):
        self.payload = payload
        self.fail = fail

    def provider(self):
        return "telegram"

    def enabled(self):
        return True

    def message_limit(self):
        return 4096

    async def send(self, conversation_id, text):
        return "1"

    async def edit(self, conversation_id, message_id, text):
        pass

    async def download(self, attachment):
        if self.fail:
            raise RuntimeError("simulated download failure")
        return self.payload


class StubVoice:
    def __init__(self, text: str = "two hundred grams of chicken", fail: bool = False):
        self.text = text
        self.fail = fail

    async def transcribe(self, data, mime_type):
        if self.fail:
            raise RuntimeError("simulated transcription failure")
        return self.text


class StubMedia:
    def __init__(self, text: str = "Oat bar, 180 kcal", fail: bool = False):
        self.text = text
        self.fail = fail

    async def extract(self, data, mime_type, media_type):
        if self.fail:
            raise RuntimeError("simulated extraction failure")
        return self.text


class ReceiptJournal:
    """Small journal double that exposes the final user-facing receipt text."""

    default_timezone = "Europe/Bucharest"

    async def handle(self, session, user, chat_id, message, *, media_kind=None, media_text=None, media_caption=None):
        if media_kind == "voice":
            return f"I heard: {media_text}\nLogged: eggs — 140 kcal\nSend Undo within 10 minutes."
        if media_kind == "photo":
            return f"Photo: {media_text}\nLogged: meal — 300 kcal\nSend Undo within 10 minutes."
        if media_kind == "voice_caption_only":
            return f"Voice caption (no transcript): {media_caption}\nLogged: meal — 300 kcal\nSend Undo within 10 minutes."
        return "Logged: meal — 300 kcal"


@pytest_asyncio.fixture(autouse=True)
async def _allow_test_user(monkeypatch):
    """Exercise the durable access policy with an explicitly granted account."""
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_frontend_enabled", True)
    now = datetime.now(UTC)
    async with session_scope() as session:
        session.add(
            TelegramAccessGrant(
                telegram_user_id=901,
                is_admin=False,
                active=True,
                granted_by=None,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    yield


def _voice_message(event_id: str) -> InboundMessage:
    return InboundMessage(
        provider="telegram", event_id=event_id, user_id="901", conversation_id="901", display_name="Tester",
        language_code="en", text=None, caption=None,
        attachments=[Attachment(AttachmentKind.VOICE, "file123", "audio/ogg")],
    )


@pytest.mark.asyncio
async def test_voice_note_is_transcribed_and_routed_through_the_journal():
    journal = ReceiptJournal()
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([StubFrontend()]), voice=StubVoice(text="how many calories today"))

    async with session_scope() as session:
        await ingress.accept(session, _voice_message("evt-voice"))

    await inbox_worker.process_one(deps)

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    assert [r.text for r in rows] == [
        "I heard: how many calories today\nLogged: eggs — 140 kcal\nSend Undo within 10 minutes."
    ]


@pytest.mark.asyncio
async def test_photo_is_extracted_and_routed_through_the_journal():
    journal = ReceiptJournal()
    assessment = "Interpretation: oat bar\nEstimate: one bar\nConfidence: high\nQuestion: none"
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([StubFrontend()]), media=StubMedia(text=assessment))
    message = InboundMessage(
        provider="telegram", event_id="evt-photo", user_id="901", conversation_id="901", display_name="Tester",
        language_code="en", text=None, caption=None,
        attachments=[Attachment(AttachmentKind.PHOTO, "photo123", "image/jpeg")],
    )
    async with session_scope() as session:
        await ingress.accept(session, message)

    await inbox_worker.process_one(deps)

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    assert [r.text for r in rows] == [
        f"Photo: {assessment}\nLogged: meal — 300 kcal\nSend Undo within 10 minutes."
    ]


@pytest.mark.asyncio
async def test_media_download_failure_gets_a_graceful_fallback_reply():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([StubFrontend(fail=True)]), voice=StubVoice())

    async with session_scope() as session:
        await ingress.accept(session, _voice_message("evt-fail"))

    await inbox_worker.process_one(deps)

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    assert [r.text for r in rows] == ["I could not transcribe that voice note. Please resend it or type the meal details."]


@pytest.mark.asyncio
async def test_missing_voice_client_gets_a_graceful_fallback_reply():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([StubFrontend()]))  # voice=None

    async with session_scope() as session:
        await ingress.accept(session, _voice_message("evt-noclient"))

    await inbox_worker.process_one(deps)

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    assert [r.text for r in rows] == ["I could not transcribe that voice note. Please resend it or type the meal details."]


@pytest.mark.asyncio
async def test_captioned_voice_survives_a_transcription_failure_with_an_honest_receipt():
    journal = ReceiptJournal()
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([StubFrontend()]), voice=StubVoice(fail=True))
    message = replace(_voice_message("evt-caption-fail"), caption="two eggs")

    async with session_scope() as session:
        await ingress.accept(session, message)

    await inbox_worker.process_one(deps)

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    assert [r.text for r in rows] == [
        "Voice caption (no transcript): two eggs\nLogged: meal — 300 kcal\nSend Undo within 10 minutes."
    ]
