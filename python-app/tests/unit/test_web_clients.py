import httpx
import pytest

from app.integrations.browserless import BrowserlessClient
from app.integrations.searxng import SearxngClient


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
async def test_browserless_strips_html_and_truncates():
    def handler(request: httpx.Request) -> httpx.Response:
        long_body = "word " * 2000
        return httpx.Response(200, text=f"<html><head><style>.x{{}}</style></head><body><script>evil()</script><p>{long_body}&amp; more</p></body></html>")

    http = httpx.AsyncClient(base_url="https://bl.example", transport=httpx.MockTransport(handler))
    client = BrowserlessClient("https://bl.example", http=http)
    text = await client.fetch_text("https://example.com/page")
    assert text is not None
    assert "<" not in text
    assert "evil()" not in text
    assert len(text) <= 4000


@pytest.mark.asyncio
async def test_browserless_swallows_errors_and_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    http = httpx.AsyncClient(base_url="https://bl.example", transport=httpx.MockTransport(handler))
    client = BrowserlessClient("https://bl.example", http=http)
    assert await client.fetch_text("https://example.com") is None
