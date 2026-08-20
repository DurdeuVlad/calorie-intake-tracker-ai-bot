"""Voice transcription via the OpenAI Audio API, ported from
OpenAiVoiceTranscriber.java."""

import httpx

from app.config import Settings
from app.domain.media_exceptions import MediaProcessingCategory, MediaProcessingException

MAX_VOICE_BYTES = 20_000_000


def _provider_failure(response: httpx.Response, cause: Exception) -> MediaProcessingException:
    status = response.status_code
    if status in (401, 403):
        return MediaProcessingException(MediaProcessingCategory.NOT_CONFIGURED, "OpenAI transcription is not configured", cause)
    if status == 404:
        return MediaProcessingException(MediaProcessingCategory.MODEL_UNAVAILABLE, "OpenAI transcription model is unavailable", cause)
    if status == 429:
        return MediaProcessingException(MediaProcessingCategory.RATE_LIMITED, "OpenAI is rate limited", cause)
    if status >= 500:
        return MediaProcessingException(MediaProcessingCategory.PROVIDER_TEMPORARY, "OpenAI is temporarily unavailable", cause)
    return MediaProcessingException(MediaProcessingCategory.PROVIDER_RESPONSE, "OpenAI rejected the transcription request", cause)


class OpenAiVoiceTranscriber:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http or httpx.AsyncClient(base_url="https://api.openai.com/v1", timeout=httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0))

    async def transcribe(self, data: bytes, mime_type: str | None) -> str:
        if not self._settings.openai_api_key:
            raise MediaProcessingException(MediaProcessingCategory.NOT_CONFIGURED, "OpenAI transcription is not configured")
        if not data or len(data) > MAX_VOICE_BYTES:
            raise MediaProcessingException(MediaProcessingCategory.INVALID_MEDIA, "Voice note is invalid")

        files = {"file": ("voice.ogg", data, mime_type or "audio/ogg")}
        form = {"model": self._settings.openai_transcription_model}
        try:
            response = await self._http.post(
                "/audio/transcriptions", headers={"Authorization": f"Bearer {self._settings.openai_api_key}"}, data=form, files=files
            )
            response.raise_for_status()
            text = (response.json().get("text") or "").strip()
            if not text:
                raise MediaProcessingException(MediaProcessingCategory.PROVIDER_RESPONSE, "OpenAI returned no transcript")
            return text
        except MediaProcessingException:
            raise
        except httpx.HTTPStatusError as failure:
            raise _provider_failure(failure.response, failure) from failure
        except httpx.TransportError as failure:
            raise MediaProcessingException(MediaProcessingCategory.PROVIDER_TEMPORARY, "OpenAI is temporarily unavailable", failure) from failure
        except Exception as failure:  # noqa: BLE001
            raise MediaProcessingException(MediaProcessingCategory.PROVIDER_RESPONSE, "OpenAI returned an invalid transcription response", failure) from failure

    async def close(self) -> None:
        await self._http.aclose()
