"""Bounded reads for untrusted HTTP provider responses."""

import json
from typing import Any

import httpx

from app.db.constraints import MAX_EXTERNAL_RESPONSE_BYTES


class ExternalResponseTooLarge(ValueError):
    """Raised when a provider response exceeds the application safety bound."""


async def read_bounded_bytes(response: httpx.Response) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_EXTERNAL_RESPONSE_BYTES:
                raise ExternalResponseTooLarge("Provider response is too large")
        except ValueError as failure:
            raise ExternalResponseTooLarge("Provider response has an invalid size") from failure

    content = bytearray()
    async for chunk in response.aiter_bytes():
        if len(content) + len(chunk) > MAX_EXTERNAL_RESPONSE_BYTES:
            raise ExternalResponseTooLarge("Provider response is too large")
        content.extend(chunk)
    return bytes(content)


async def request_bounded_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> Any:
    async with client.stream(method, url, **kwargs) as response:
        response.raise_for_status()
        content = await read_bounded_bytes(response)
    try:
        return json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as failure:
        raise ValueError("Provider returned invalid JSON") from failure
