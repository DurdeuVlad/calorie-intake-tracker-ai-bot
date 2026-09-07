"""Self-hosted Browserless page fetch with a defense-in-depth SSRF boundary.

The caller supplies the same async URL validator used for redirect resolution.
The Browserless request also disables JavaScript, narrows navigation to the
already-validated final hostname, and requires an operator-controlled filtering
proxy so browser-side redirects cannot silently leave the validated origin or
reach private networks. Deployments must restrict Browserless egress to public
web destinations and explicitly opt in with ``egress_restricted`` plus a proxy;
this client fails closed otherwise or when no validator is configured.
"""

import re
from collections.abc import Awaitable, Callable

import httpx

from app.db.constraints import MAX_EXTERNAL_RESPONSE_BYTES

UrlValidator = Callable[[str], Awaitable[bool]]

MAX_CONTENT_CHARS = 4000
BROWSERLESS_CONNECT_TIMEOUT_SECONDS = 10.0
BROWSERLESS_READ_TIMEOUT_SECONDS = 30.0
BROWSERLESS_WRITE_TIMEOUT_SECONDS = 10.0
BROWSERLESS_POOL_TIMEOUT_SECONDS = 5.0

_TAG_BLOCK_RE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")
_TAG_RE = re.compile(r"(?s)<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_UNESCAPES = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'"}
_BROWSERLESS_REJECT_REQUEST_PATTERNS = (
    r"^https?://(?:[^/]*@)?(?:localhost(?:[.:/]|$)|0\.|10\.|127\.|100\.(?:6[4-9]|[7-9][0-9]|1[0-1][0-9]|12[0-7])\.|169\.254\.|172\.(?:1[6-9]|2[0-9]|3[0-1])\.|192\.(?:0\.|168\.)|198\.(?:18|19|51\.100)\.|203\.0\.113\.|240\.|\[(?:::1|::ffff:|fc[0-9a-fA-F]*:|fd[0-9a-fA-F]*:|fe[89a-fA-F][0-9a-fA-F]*:))",
    r"^https?://(?:[^/]*@)?(?:[0-9]+(?:\.[0-9]+){0,3}|0x[0-9a-fA-F]+)(?::\d+)?(?:/|$)",
)


def _strip_html(html: str | None) -> str:
    if not html:
        return ""
    without_scripts = _TAG_BLOCK_RE.sub("", html)
    without_tags = _TAG_RE.sub(" ", without_scripts)
    for escaped, replacement in _UNESCAPES.items():
        without_tags = without_tags.replace(escaped, replacement)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


async def _read_bounded_response(response: httpx.Response) -> str | None:
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_EXTERNAL_RESPONSE_BYTES:
                return None
        except ValueError:
            return None

    content = bytearray()
    async for chunk in response.aiter_bytes():
        if len(content) + len(chunk) > MAX_EXTERNAL_RESPONSE_BYTES:
            return None
        content.extend(chunk)

    try:
        return bytes(content).decode(response.encoding or "utf-8", errors="replace")
    except (LookupError, ValueError):
        return None


class BrowserlessClient:
    def __init__(
        self,
        base_url: str,
        token: str = "",
        http: httpx.AsyncClient | None = None,
        url_validator: UrlValidator | None = None,
        egress_restricted: bool = False,
        egress_proxy_url: str = "",
    ) -> None:
        self._egress_proxy_url = egress_proxy_url.strip()
        try:
            proxy = httpx.URL(self._egress_proxy_url) if self._egress_proxy_url else None
            valid_proxy = (
                proxy is not None
                and proxy.scheme in {"http", "https"}
                and bool(proxy.host)
                and not proxy.username
                and not proxy.password
            )
        except (TypeError, ValueError, httpx.InvalidURL):
            valid_proxy = False
        self._enabled = bool(base_url and base_url.strip() and egress_restricted and valid_proxy)
        self._token = token or ""
        self._url_validator = url_validator
        self._http = http or (
            httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(
                    connect=BROWSERLESS_CONNECT_TIMEOUT_SECONDS,
                    read=BROWSERLESS_READ_TIMEOUT_SECONDS,
                    write=BROWSERLESS_WRITE_TIMEOUT_SECONDS,
                    pool=BROWSERLESS_POOL_TIMEOUT_SECONDS,
                ),
                trust_env=False,
            )
            if self._enabled
            else None
        )

    async def fetch_text(self, url: str | None, *, allowed_domain: str | None = None) -> str | None:
        if not self._enabled or not url or not url.strip() or self._url_validator is None:
            return None
        try:
            parsed = httpx.URL(url)
            normalized_url = str(parsed)
            if not await self._url_validator(normalized_url):
                return None
            if not allowed_domain or parsed.host.casefold() != allowed_domain.casefold() or any(
                char in allowed_domain for char in "\r\n\t /\\"
            ):
                return None
            allowed_domain = parsed.host
            params: list[tuple[str, str]] = [("token", self._token)] if self._token else []
            # Browserless uses this allow-list for all subsequent navigation
            # requests, including HTTP redirects. The proxy is mandatory when
            # this client is enabled; it is the deployment-enforced egress
            # boundary rather than a self-attested application check.
            params.extend(
                [
                    ("allowedDomains", allowed_domain),
                    ("externalProxyServer", self._egress_proxy_url),
                ]
            )
            async with self._http.stream(
                "POST",
                "/content",
                params=params,
                json={
                    "url": normalized_url,
                    "setJavaScriptEnabled": False,
                    "rejectRequestPattern": list(_BROWSERLESS_REJECT_REQUEST_PATTERNS),
                },
            ) as response:
                response.raise_for_status()
                html = await _read_bounded_response(response)
            if html is None:
                return None
            text = _strip_html(html)
            if not text:
                return None
            return text[:MAX_CONTENT_CHARS]
        except Exception:  # noqa: BLE001 - graceful degradation, matches Java's catch(Exception ignored)
            return None

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
