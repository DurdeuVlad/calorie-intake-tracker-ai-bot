"""Photo/PDF food-evidence extraction via the OpenAI Responses API, ported from
OpenAiFoodMediaExtractor.java. The model never mutates the journal directly --
this returns plain extracted text that gets fed back into the agent as a
normal user message."""

import base64
from enum import Enum

import httpx

from app.config import Settings
from app.domain.media_exceptions import (
    MediaProcessingCategory,
    MediaProcessingException,
)

MAX_MEDIA_BYTES = 20_000_000


class FoodMediaType(str, Enum):
    PHOTO = "PHOTO"
    DOCUMENT = "DOCUMENT"


def _prompt(media_type: FoodMediaType) -> str:
    if media_type is FoodMediaType.DOCUMENT:
        return (
            "Read this food-related PDF. Extract only food and nutrition-label evidence that is actually visible. "
            "State food names, portions, serving sizes, calories and macros only when legible. Do not invent "
            "missing values. Return a concise plain-text meal description suitable for a food journal."
        )

    return """Analyze this food photo visually. This is not an OCR-only task: identify the actual plated, prepared,
or packaged food from its appearance, even if there is no readable text. Use visible text only as supporting evidence.

Return exactly these concise sections:
Interpretation: the most likely food or dish, including visible components and preparation when distinguishable.
Estimate: a rough visible portion (household measure or grams only when reasonably inferable); say "portion unclear"
when the image provides no reliable scale.
Confidence: high, medium, or low, followed by a short reason grounded in what is visible.
Question: one specific question only if the answer would materially change the food or portion estimate; otherwise "none".

Do not claim an exact weight, nutrition value, recipe, or brand unless it is visible. If the image is packaging or a
nutrition label, identify the product only from legible evidence and distinguish serving information from what was
actually eaten. If it is not food or cannot be interpreted, say so plainly with low confidence."""


def _supported_mime_type(mime_type: str | None, media_type: FoodMediaType) -> str:
    if media_type is FoodMediaType.PHOTO:
        if not mime_type:
            return "image/jpeg"
        if mime_type.startswith("image/"):
            return mime_type
    if media_type is FoodMediaType.DOCUMENT and mime_type == "application/pdf":
        return mime_type
    raise MediaProcessingException(MediaProcessingCategory.INVALID_MEDIA, "Unsupported media type")


def _provider_failure(response: httpx.Response, cause: Exception) -> MediaProcessingException:
    status = response.status_code
    if status in (401, 403):
        return MediaProcessingException(MediaProcessingCategory.NOT_CONFIGURED, "OpenAI media extraction is not configured", cause)
    if status == 404:
        return MediaProcessingException(MediaProcessingCategory.MODEL_UNAVAILABLE, "OpenAI media model is unavailable", cause)
    if status == 429:
        return MediaProcessingException(MediaProcessingCategory.RATE_LIMITED, "OpenAI is rate limited", cause)
    if status >= 500:
        return MediaProcessingException(MediaProcessingCategory.PROVIDER_TEMPORARY, "OpenAI media extraction is temporarily unavailable", cause)
    return MediaProcessingException(MediaProcessingCategory.PROVIDER_RESPONSE, "OpenAI rejected the media extraction request", cause)


def _output_text(payload: dict) -> str:
    for output in payload.get("output", []) or []:
        for content in output.get("content", []) or []:
            if content.get("type") == "output_text":
                text = (content.get("text") or "").strip()
                if text:
                    return text
    raise MediaProcessingException(MediaProcessingCategory.PROVIDER_RESPONSE, "OpenAI returned no media extraction")


class OpenAiFoodMediaExtractor:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http or httpx.AsyncClient(base_url="https://api.openai.com/v1", timeout=httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0))

    async def extract(self, data: bytes, mime_type: str | None, media_type: FoodMediaType) -> str:
        if not self._settings.openai_api_key:
            raise MediaProcessingException(MediaProcessingCategory.NOT_CONFIGURED, "OpenAI media extraction is not configured")
        safe_mime = _supported_mime_type(mime_type, media_type)
        if not data or len(data) > MAX_MEDIA_BYTES:
            raise MediaProcessingException(MediaProcessingCategory.INVALID_MEDIA, "Media payload is invalid")

        encoded = f"data:{safe_mime};base64,{base64.b64encode(data).decode('ascii')}"
        media_part = (
            {"type": "input_image", "image_url": encoded, "detail": "auto"}
            if media_type is FoodMediaType.PHOTO
            else {"type": "input_file", "filename": "document.pdf", "file_data": encoded}
        )
        body = {
            "model": self._settings.openai_model,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": _prompt(media_type)}, media_part]}],
            "max_output_tokens": 600,
        }
        try:
            response = await self._http.post("/responses", headers={"Authorization": f"Bearer {self._settings.openai_api_key}"}, json=body)
            response.raise_for_status()
            return _output_text(response.json())
        except MediaProcessingException:
            raise
        except httpx.HTTPStatusError as failure:
            raise _provider_failure(failure.response, failure) from failure
        except httpx.TransportError as failure:
            raise MediaProcessingException(MediaProcessingCategory.PROVIDER_TEMPORARY, "OpenAI media extraction is temporarily unavailable", failure) from failure
        except Exception as failure:
            raise MediaProcessingException(MediaProcessingCategory.PROVIDER_RESPONSE, "OpenAI returned an invalid media extraction response", failure) from failure

    async def close(self) -> None:
        await self._http.aclose()
