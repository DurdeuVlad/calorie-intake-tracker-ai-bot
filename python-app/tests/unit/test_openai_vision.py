import json

import httpx
import pytest

from app.config import Settings
from app.domain.media_exceptions import (
    MediaProcessingCategory,
    MediaProcessingException,
)
from app.integrations.openai_vision import FoodMediaType, OpenAiFoodMediaExtractor


def _response(text: str) -> dict:
    return {"output": [{"content": [{"type": "output_text", "text": text}]}]}


async def _extract_with(handler, provider_text: str) -> tuple[str, dict]:
    captured: dict = {}

    async def transport(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return handler(request, provider_text)

    client = httpx.AsyncClient(base_url="https://api.openai.com/v1", transport=httpx.MockTransport(transport))
    extractor = OpenAiFoodMediaExtractor(Settings(openai_api_key="test-key"), http=client)
    try:
        result = await extractor.extract(b"not-an-ocr-fixture", "image/jpeg", FoodMediaType.PHOTO)
    finally:
        await extractor.close()
    return result, captured


@pytest.mark.asyncio
async def test_clear_food_photo_is_sent_as_vision_and_preserves_visual_interpretation():
    visual_assessment = (
        "Interpretation: grilled chicken breast with roasted vegetables.\n"
        "Estimate: about one palm-sized chicken breast and one cup vegetables.\n"
        "Confidence: high; the plated foods are clearly visible.\n"
        "Question: none"
    )

    result, body = await _extract_with(
        lambda request, text: httpx.Response(200, json=_response(text)), visual_assessment
    )

    assert result == visual_assessment
    content = body["input"][0]["content"]
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/jpeg;base64,")
    prompt = content[0]["text"].lower()
    assert "not an ocr-only task" in prompt
    assert "plated, prepared" in prompt
    assert "interpretation:" in prompt
    assert "confidence:" in prompt


@pytest.mark.asyncio
async def test_packaging_photo_distinguishes_label_serving_from_food_eaten():
    label_assessment = (
        "Interpretation: a packaged oat bar; the front label identifies the product.\n"
        "Estimate: portion unclear; the image does not show whether the whole bar was eaten.\n"
        "Confidence: medium; packaging and label are visible.\n"
        "Question: Did you eat the whole bar or a portion of it?"
    )

    result, body = await _extract_with(
        lambda request, text: httpx.Response(200, json=_response(text)), label_assessment
    )

    assert result == label_assessment
    prompt = body["input"][0]["content"][0]["text"].lower()
    assert "packaging or a" in prompt
    assert "serving information from what was" in prompt


@pytest.mark.asyncio
async def test_prompt_asks_for_a_legible_printed_label_value_separate_from_the_estimate():
    """Live production gap: a photo whose vision interpretation said "nutrition
    facts are visible" still only produced a rough visual guess (~120 kcal),
    forcing the user to retype the actual printed number (169 kcal) by hand.
    The prompt never asked the model to report a legible printed value at all."""
    label_assessment = (
        "Interpretation: a packaged yogurt drink; the nutrition panel is visible on the back.\n"
        "Estimate: one 250 ml pouch.\n"
        "Label: 169 kcal per 250 ml serving.\n"
        "Confidence: high; the printed nutrition panel is legible.\n"
        "Question: none"
    )

    result, body = await _extract_with(
        lambda request, text: httpx.Response(200, json=_response(text)), label_assessment
    )

    assert result == label_assessment
    prompt = body["input"][0]["content"][0]["text"]
    assert "Label: any calorie or nutrition value actually printed and legible" in prompt
    assert 'say "none" if no legible printed value' in prompt
    assert "Never invent, round, or estimate a value here" in prompt


@pytest.mark.asyncio
async def test_ambiguous_photo_requires_one_specific_question_not_a_guessed_meal():
    ambiguous_assessment = (
        "Interpretation: a bowl containing a pale soup or sauce; ingredients are not distinguishable.\n"
        "Estimate: portion unclear.\n"
        "Confidence: low; the image lacks detail and scale.\n"
        "Question: Was this soup, yogurt, or another dish, and roughly how much did you have?"
    )

    result, _ = await _extract_with(
        lambda request, text: httpx.Response(200, json=_response(text)), ambiguous_assessment
    )

    assert result == ambiguous_assessment
    assert "low" in result
    assert "Question: Was this" in result


@pytest.mark.asyncio
async def test_vision_provider_failure_is_classified_without_exposing_image_data():
    async def failed_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "temporarily unavailable"}})

    client = httpx.AsyncClient(base_url="https://api.openai.com/v1", transport=httpx.MockTransport(failed_transport))
    extractor = OpenAiFoodMediaExtractor(Settings(openai_api_key="test-key"), http=client)
    try:
        with pytest.raises(MediaProcessingException) as failure:
            await extractor.extract(b"private-image-bytes", "image/jpeg", FoodMediaType.PHOTO)
    finally:
        await extractor.close()

    assert failure.value.category is MediaProcessingCategory.PROVIDER_TEMPORARY
    assert "private-image-bytes" not in str(failure.value)
