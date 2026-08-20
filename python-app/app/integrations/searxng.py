"""Self-hosted SearxNG search, ported from SearxngClient.java. Finds nutrition
facts Open Food Facts does not carry (restaurant/menu items). Optional --
returns [] (never raises) when SEARXNG_BASE_URL is unset."""

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str


class SearxngClient:
    def __init__(self, base_url: str, http: httpx.AsyncClient | None = None) -> None:
        self._enabled = bool(base_url and base_url.strip())
        self._http = http or (
            httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0))
            if self._enabled
            else None
        )

    async def search(self, query: str | None) -> list[WebSearchResult]:
        if not self._enabled or not query or not query.strip():
            return []
        try:
            response = await self._http.get("/search", params={"q": query, "format": "json"})
            response.raise_for_status()
            results = response.json().get("results")
            if not isinstance(results, list):
                return []
            mapped: list[WebSearchResult] = []
            for result in results:
                title = str(result.get("title", "")).strip()
                url = str(result.get("url", "")).strip()
                snippet = str(result.get("content", ""))
                if not title or not url:
                    continue
                mapped.append(WebSearchResult(title, url, snippet))
                if len(mapped) >= 5:
                    break
            return mapped
        except Exception:  # noqa: BLE001 - graceful degradation, matches Java's catch(Exception ignored)
            return []

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
