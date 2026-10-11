"""POST /api/v1/messages -- the mobile app's core call (audit section 4.1).

Accepts either JSON {text} or multipart audio (opus/m4a). Audio is transcribed
through the same OpenAiVoiceTranscriber the Telegram voice notes use, held in
memory only and never stored. The text (or transcript) runs through the
existing journal agent synchronously -- the app waits for the reply in-request,
so nothing goes through the inbox/outbox delivery path.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from app.db.base import session_scope
from app.domain.media_exceptions import MediaProcessingCategory, MediaProcessingException
from app.integrations.openai_transcription import MAX_VOICE_BYTES
from app.mobile import journal_turn
from app.mobile.dependencies import MobilePrincipal, get_current_account
from app.mobile.rate_limit import message_rate_limit
from app.mobile.schemas import JournalActionResult, MessageRequest, MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/messages", tags=["mobile-messages"])

_rate_limited = [Depends(message_rate_limit)]

# Multipart framing overhead allowance on top of the raw audio cap.
_MAX_MULTIPART_BYTES = MAX_VOICE_BYTES + 65_536

_TRANSCRIPTION_STATUS = {
    MediaProcessingCategory.INVALID_MEDIA: 422,
    MediaProcessingCategory.NOT_CONFIGURED: 503,
    MediaProcessingCategory.MODEL_UNAVAILABLE: 503,
    MediaProcessingCategory.RATE_LIMITED: 503,
    MediaProcessingCategory.PROVIDER_TEMPORARY: 503,
    MediaProcessingCategory.PROVIDER_RESPONSE: 502,
    MediaProcessingCategory.TELEGRAM_DOWNLOAD: 502,
}


def _parse_json_text(raw: bytes) -> str:
    try:
        return MessageRequest.model_validate(json.loads(raw)).text
    except (ValidationError, ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="invalid message body") from None


async def _transcribe_form(request: Request, deps: journal_turn.MobileJournalDeps) -> str:
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > _MAX_MULTIPART_BYTES:
        raise HTTPException(status_code=413, detail="audio exceeds the 20 MB limit")

    form = await request.form()
    upload = form.get("audio")
    if not isinstance(upload, UploadFile):
        raise HTTPException(status_code=422, detail="multipart request must include an 'audio' file")

    data = await upload.read()
    if len(data) > MAX_VOICE_BYTES:
        raise HTTPException(status_code=413, detail="audio exceeds the 20 MB limit")
    if deps.voice is None:
        raise HTTPException(status_code=503, detail="voice transcription is not configured")
    try:
        text = await deps.voice.transcribe(data, upload.content_type)
    except MediaProcessingException as failure:
        logger.warning("Mobile audio transcription failed: category=%s", failure.category)
        status = _TRANSCRIPTION_STATUS.get(failure.category, 502)
        raise HTTPException(status_code=status, detail="audio transcription failed") from None

    # Mirrors the inbox worker: an optional text field on the form is appended
    # to the transcript the same way a Telegram caption is.
    caption = form.get("caption") or form.get("text")
    if isinstance(caption, str) and caption.strip():
        return f"{text}\nUser caption: {caption.strip()[:4096]}"
    return text


async def _extract_text(request: Request, deps: journal_turn.MobileJournalDeps) -> str:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type == "application/json":
        return _parse_json_text(await request.body())
    if content_type == "multipart/form-data":
        return await _transcribe_form(request, deps)
    raise HTTPException(status_code=415, detail="send application/json {text} or multipart/form-data audio")


@router.post("", response_model=MessageResponse, dependencies=_rate_limited)
async def post_message(
    request: Request,
    principal: MobilePrincipal = Depends(get_current_account),
    deps: journal_turn.MobileJournalDeps = Depends(journal_turn.get_message_deps),
) -> MessageResponse:
    text = await _extract_text(request, deps)

    # chat_id is used by the tool executor's pinned-status path via int(chat_id),
    # so it must stay numeric -- the account id doubles as the conversation id
    # for the single app<->agent conversation.
    chat_id = str(principal.account.id)
    async with session_scope() as session:
        try:
            turn = await journal_turn.run_turn(session, principal.user, chat_id, text, deps)
        except Exception:
            logger.exception("Mobile journal turn failed: account_id=%s", principal.account.id)
            raise HTTPException(
                status_code=502, detail="the journal agent could not process this message"
            ) from None
        await session.commit()

    return MessageResponse(
        reply=turn.reply,
        actions=[JournalActionResult.from_tool_row(row) for row in turn.actions],
    )
