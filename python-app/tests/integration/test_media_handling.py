"""Attachment handling in the inbox worker: download -> transcribe/extract ->
feed the resulting text through the normal message pipeline, or reply with a
graceful fallback if anything in that chain fails -- mirrors
MessagingInboxWorker.process()'s attachment branch exactly."""

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db.base import session_scope
from app.db.models.messaging import MessagingOutboundMessage
from app.messaging import ingress, inbox_worker
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


@pytest.fixture(autouse=True)
def _allow_test_user(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(type(settings), "allowed_telegram_user_id_set", property(lambda self: {"901"}))
    yield


def _voice_message(event_id: str) -> InboundMessage:
    return InboundMessage(
        provider="telegram", event_id=event_id, user_id="901", conversation_id="901", display_name="Tester",
        language_code="en", text=None, caption=None,
        attachments=[Attachment(AttachmentKind.VOICE, "file123", "audio/ogg")],
    )


@pytest.mark.asyncio
async def test_voice_note_is_transcribed_and_routed_through_the_journal():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")  # no agent -> canned reply
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([StubFrontend()]), voice=StubVoice(text="how many calories today"))

    async with session_scope() as session:
        await ingress.accept(session, _voice_message("evt-voice"))

    await inbox_worker.process_one(deps)

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    assert any("cannot process" in r.text for r in rows)  # reached the journal (no agent configured in this test)


@pytest.mark.asyncio
async def test_photo_is_extracted_and_routed_through_the_journal():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([StubFrontend()]), media=StubMedia(text="Oat bar, 180 kcal"))
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
    assert len(rows) == 1  # got a reply at all -> extraction succeeded and reached the journal


@pytest.mark.asyncio
async def test_media_download_failure_gets_a_graceful_fallback_reply():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([StubFrontend(fail=True)]), voice=StubVoice())

    async with session_scope() as session:
        await ingress.accept(session, _voice_message("evt-fail"))

    await inbox_worker.process_one(deps)

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    assert any("could not analyze" in r.text for r in rows)


@pytest.mark.asyncio
async def test_missing_voice_client_gets_a_graceful_fallback_reply():
    journal = JournalApplicationService(default_timezone="Europe/Bucharest")
    deps = InboxWorkerDeps(journal=journal, frontends=FrontendRegistry([StubFrontend()]))  # voice=None

    async with session_scope() as session:
        await ingress.accept(session, _voice_message("evt-noclient"))

    await inbox_worker.process_one(deps)

    async with session_scope() as session:
        rows = (await session.execute(select(MessagingOutboundMessage))).scalars().all()
    assert any("could not analyze" in r.text for r in rows)
