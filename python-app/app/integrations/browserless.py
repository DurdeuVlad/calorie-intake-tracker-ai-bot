"""Self-hosted Browserless page fetch, ported from BrowserlessClient.java. Used
when a search snippet lacks a usable number. Optional -- returns None (never
raises) when BROWSERLESS_BASE_URL is unset. The caller (journal_tool_executor's
fetch_web_page tool) is responsible for SSRF validation BEFORE calling this;
this client does not re-validate the URL itself."""

import re

import httpx

MAX_LENGTH = 4000

_TAG_BLOCK_RE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")
_TAG_RE = re.compile(r"(?s)<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_UNESCAPES = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'"}


def _strip_html(html: str | None) -> str:
    if not html:
        return ""
    without_scripts = _TAG_BLOCK_RE.sub("", html)
    without_tags = _TAG_RE.sub(" ", without_scripts)
    for escaped, replacement in _UNESCAPES.items():
        without_tags = without_tags.replace(escaped, replacement)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


class BrowserlessClient:
    def __init__(self, base_url: str, token: str = "", http: httpx.AsyncClient | None = None) -> None:
        self._enabled = bool(base_url and base_url.strip())
        self._token = token or ""
        self._http = http or (
            httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0))
            if self._enabled
            else None
        )

    async def fetch_text(self, url: str | None) -> str | None:
        if not self._enabled or not url or not url.strip():
            return None
        try:
            params = {"token": self._token} if self._token else None
            response = await self._http.post("/content", params=params, json={"url": url})
            response.raise_for_status()
            text = _strip_html(response.text)
            if not text:
                return None
            return text[:MAX_LENGTH]
        except Exception:  # noqa: BLE001 - graceful degradation, matches Java's catch(Exception ignored)
            return None

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
