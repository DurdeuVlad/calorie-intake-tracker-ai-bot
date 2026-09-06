import json

import httpx
import pytest

from app.integrations.browserless import (
    MAX_CONTENT_CHARS,
    MAX_EXTERNAL_RESPONSE_BYTES,
    BrowserlessClient,
)
from app.integrations.http_response import (
    ExternalResponseTooLarge,
    request_bounded_json,
)
from app.integrations.searxng import SearxngClient


@pytest.mark.asyncio
async def test_bounded_json_request_rejects_oversized_provider_responses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (MAX_EXTERNAL_RESPONSE_BYTES + 1))

    http = httpx.AsyncClient(base_url="https://provider.example", transport=httpx.MockTransport(handler))
    with pytest.raises(ExternalResponseTooLarge):
        await request_bounded_json(http, "GET", "/payload")
    await http.aclose()


@pytest.mark.asyncio
async def test_bounded_json_request_rejects_oversized_streamed_body_without_content_length():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"transfer-encoding": "chunked"},
            content=b"x" * (MAX_EXTERNAL_RESPONSE_BYTES + 1),
        )

    http = httpx.AsyncClient(base_url="https://provider.example", transport=httpx.MockTransport(handler))
    with pytest.raises(ExternalResponseTooLarge):
        await request_bounded_json(http, "GET", "/payload")
    await http.aclose()


@pytest.mark.asyncio
async def test_bounded_json_request_rejects_invalid_content_length_header():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-length": "not-a-number"}, content=b"{}")

    http = httpx.AsyncClient(base_url="https://provider.example", transport=httpx.MockTransport(handler))
    with pytest.raises(ExternalResponseTooLarge):
        await request_bounded_json(http, "GET", "/payload")
    await http.aclose()


@pytest.mark.asyncio
async def test_bounded_json_request_returns_parsed_json_for_valid_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    http = httpx.AsyncClient(base_url="https://provider.example", transport=httpx.MockTransport(handler))
    payload = await request_bounded_json(http, "GET", "/payload")
    assert payload == {"ok": True}
    await http.aclose()


@pytest.mark.asyncio
async def test_searxng_disabled_when_base_url_is_blank():
    client = SearxngClient("")
    assert await client.search("pizza") == []


@pytest.mark.asyncio
async def test_searxng_returns_up_to_five_results():
    def handler(request: httpx.Request) -> httpx.Response:
        results = [{"title": f"Result {i}", "url": f"https://example.com/{i}", "content": "snippet"} for i in range(8)]
        return httpx.Response(200, json={"results": results})

    http = httpx.AsyncClient(base_url="https://searx.example", transport=httpx.MockTransport(handler))
    client = SearxngClient("https://searx.example", http=http)
    results = await client.search("pizza")
    assert len(results) == 5


@pytest.mark.asyncio
async def test_searxng_skips_results_missing_title_or_url():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"title": "", "url": "https://example.com"}, {"title": "OK", "url": ""}, {"title": "Good", "url": "https://example.com/good", "content": "x"}]})

    http = httpx.AsyncClient(base_url="https://searx.example", transport=httpx.MockTransport(handler))
    client = SearxngClient("https://searx.example", http=http)
    results = await client.search("pizza")
    assert len(results) == 1
    assert results[0].title == "Good"


@pytest.mark.asyncio
async def test_searxng_swallows_errors_and_returns_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    http = httpx.AsyncClient(base_url="https://searx.example", transport=httpx.MockTransport(handler))
    client = SearxngClient("https://searx.example", http=http)
    assert await client.search("pizza") == []


@pytest.mark.asyncio
async def test_browserless_disabled_when_base_url_is_blank():
    client = BrowserlessClient("")
    assert await client.fetch_text("https://example.com") is None


@pytest.mark.asyncio
async def test_browserless_requires_restricted_egress_proxy():
    async def allow_public_url(url: str) -> bool:
        return True

    without_proxy = BrowserlessClient(
        "https://bl.example", url_validator=allow_public_url, egress_restricted=True
    )
    with_invalid_proxy = BrowserlessClient(
        "https://bl.example",
        url_validator=allow_public_url,
        egress_restricted=True,
        egress_proxy_url="file:///tmp/proxy",
    )

    assert await without_proxy.fetch_text("https://example.com", allowed_domain="example.com") is None
    assert await with_invalid_proxy.fetch_text("https://example.com", allowed_domain="example.com") is None


@pytest.mark.asyncio
async def test_browserless_control_request_ignores_ambient_proxy_environment():
    client = BrowserlessClient(
        "https://bl.example",
        url_validator=lambda url: True,
        egress_restricted=True,
        egress_proxy_url="http://egress-proxy:8080",
    )
    assert client._http is not None
    assert client._http._trust_env is False


@pytest.mark.asyncio
async def test_browserless_strips_html_and_truncates():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get_list("allowedDomains") == ["example.com"]
        assert request.url.params.get_list("externalProxyServer") == ["http://egress-proxy:8080"]
        payload = json.loads(request.content)
        assert payload["setJavaScriptEnabled"] is False
        patterns = payload["rejectRequestPattern"]
        assert all("(?i)" not in pattern for pattern in patterns)
        assert any("1[0-1][0-9]" in pattern and "12[0-7]" in pattern for pattern in patterns)
        long_body = "word " * 2000
        return httpx.Response(200, text=f"<html><head><style>.x{{}}</style></head><body><script>evil()</script><p>{long_body}&amp; more</p></body></html>")

    async def allow_public_url(url: str) -> bool:
        return url == "https://example.com/page"

    http = httpx.AsyncClient(base_url="https://bl.example", transport=httpx.MockTransport(handler))
    client = BrowserlessClient("https://bl.example", http=http, url_validator=allow_public_url, egress_restricted=True, egress_proxy_url="http://egress-proxy:8080")
    text = await client.fetch_text("https://example.com/page", allowed_domain="example.com")
    assert text is not None
    assert "<" not in text
    assert "evil()" not in text
    assert len(text) <= MAX_CONTENT_CHARS


@pytest.mark.asyncio
async def test_browserless_rejects_oversized_responses_before_html_processing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (MAX_EXTERNAL_RESPONSE_BYTES + 1))

    async def allow_public_url(url: str) -> bool:
        return url == "https://example.com"

    http = httpx.AsyncClient(base_url="https://bl.example", transport=httpx.MockTransport(handler))
    client = BrowserlessClient(
        "https://bl.example",
        http=http,
        url_validator=allow_public_url,
        egress_restricted=True,
        egress_proxy_url="http://egress-proxy:8080",
    )
    assert await client.fetch_text("https://example.com", allowed_domain="example.com") is None


@pytest.mark.asyncio
async def test_browserless_swallows_errors_and_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async def allow_public_url(url: str) -> bool:
        return url == "https://example.com"

    http = httpx.AsyncClient(base_url="https://bl.example", transport=httpx.MockTransport(handler))
    client = BrowserlessClient("https://bl.example", http=http, url_validator=allow_public_url, egress_restricted=True, egress_proxy_url="http://egress-proxy:8080")
    assert await client.fetch_text("https://example.com", allowed_domain="example.com") is None


@pytest.mark.asyncio
async def test_browserless_fails_closed_without_validator_or_matching_domain():
    http = httpx.AsyncClient(
        base_url="https://bl.example", transport=httpx.MockTransport(lambda request: httpx.Response(200, text="ok"))
    )

    async def allow_public_url(url: str) -> bool:
        return True

    client = BrowserlessClient("https://bl.example", http=http, url_validator=allow_public_url, egress_restricted=True, egress_proxy_url="http://egress-proxy:8080")
    assert await client.fetch_text("https://example.com", allowed_domain="other.example") is None
