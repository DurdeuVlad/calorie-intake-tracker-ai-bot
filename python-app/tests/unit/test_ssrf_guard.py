"""SSRF URL validation and redirect safety checks."""

import asyncio

import pytest

from app.services.journal_tool_executor import JournalToolExecutor
from app.tools import nutrition


def _executor() -> JournalToolExecutor:
    return JournalToolExecutor()


def test_rejects_non_http_schemes():
    executor = _executor()
    assert executor._is_safe_external_url("ftp://example.com/file") is False
    assert executor._is_safe_external_url("file:///etc/passwd") is False
    assert executor._is_safe_external_url("javascript:alert(1)") is False


def test_rejects_url_with_no_host():
    executor = _executor()
    assert executor._is_safe_external_url("https:///path") is False


def test_rejects_loopback_hostnames():
    executor = _executor()
    assert executor._is_safe_external_url("http://localhost/admin") is False
    assert executor._is_safe_external_url("http://127.0.0.1/admin") is False
    assert executor._is_safe_external_url("http://[::1]/admin") is False


def test_rejects_private_and_link_local_addresses():
    executor = _executor()
    assert executor._is_safe_external_url("http://10.0.0.5/") is False
    assert executor._is_safe_external_url("http://192.168.1.1/") is False
    assert executor._is_safe_external_url("http://169.254.169.254/latest/meta-data/") is False  # cloud metadata endpoint


def test_rejects_unspecified_address():
    executor = _executor()
    assert executor._is_safe_external_url("http://0.0.0.0/") is False


def test_rejects_non_web_ports():
    executor = _executor()
    assert executor._is_safe_external_url("https://example.com:6379/") is False


def test_accepts_a_normal_public_https_url():
    executor = _executor()
    assert executor._is_safe_external_url("https://example.com/page") is True


def test_rejects_public_ip_literals_to_match_browserless_policy():
    executor = _executor()
    assert executor._is_safe_external_url("https://8.8.8.8/") is False


@pytest.mark.asyncio
async def test_async_guard_rejects_private_dns_results(monkeypatch):
    monkeypatch.setattr(
        nutrition.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("10.0.0.5", 0))],
    )

    assert await nutrition._is_safe_external_url_async("https://food.example/menu") is False


@pytest.mark.asyncio
async def test_async_dns_resolution_has_a_timeout(monkeypatch):
    async def slow_to_thread(*args, **kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(nutrition, "EXTERNAL_URL_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setattr(nutrition.asyncio, "to_thread", slow_to_thread)

    assert await nutrition._public_addresses_async("food.example") is None


def test_rejects_malformed_url():
    executor = _executor()
    assert executor._is_safe_external_url("not a url at all") is False


@pytest.mark.asyncio
async def test_redirect_probe_uses_the_validated_public_address(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def public_addresses(host: str) -> tuple[str, ...]:
        assert host == "food.example"
        return ("203.0.113.10",)

    async def pinned_request(url: str, address: str) -> tuple[int, str | None]:
        calls.append((url, address))
        return 200, None

    monkeypatch.setattr(nutrition, "_public_addresses_async", public_addresses)
    monkeypatch.setattr(nutrition, "_request_with_pinned_dns", pinned_request)

    assert await nutrition._resolve_safe_final_url("https://food.example/menu") == "https://food.example/menu"
    assert calls == [("https://food.example/menu", "203.0.113.10")]


@pytest.mark.asyncio
async def test_redirect_probe_rejects_oversized_location(monkeypatch):
    async def public_addresses(host: str) -> tuple[str, ...]:
        return ("203.0.113.10",)

    async def pinned_request(url: str, address: str) -> tuple[int, str | None]:
        return 302, "/" + ("x" * 3000)

    monkeypatch.setattr(nutrition, "_public_addresses_async", public_addresses)
    monkeypatch.setattr(nutrition, "_request_with_pinned_dns", pinned_request)

    assert await nutrition._resolve_safe_final_url("https://food.example/menu") is None


@pytest.mark.asyncio
async def test_pinned_dns_backend_connects_only_to_the_validated_address():
    class FakeBackend:
        async def connect_tcp(self, *args):
            return args

        async def connect_unix_socket(self, *args):
            return args

        async def sleep(self, seconds):
            return None

    backend = nutrition._PinnedDnsBackend("food.example", "203.0.113.10")
    backend._backend = FakeBackend()

    result = await backend.connect_tcp("food.example", 443, 5.0, None, None)

    assert result[0] == "203.0.113.10"
    with pytest.raises(OSError):
        await backend.connect_tcp("other.example", 443)


@pytest.mark.asyncio
async def test_browserless_is_disabled_without_explicit_egress_restriction():
    from app.integrations.browserless import BrowserlessClient

    client = BrowserlessClient("https://browserless.example", url_validator=lambda url: True)
    assert await client.fetch_text("https://food.example/menu", allowed_domain="food.example") is None
