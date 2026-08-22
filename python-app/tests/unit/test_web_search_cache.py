from app.domain.agent_types import ToolCall
from app.integrations.searxng import WebSearchResult
from app.services.journal_tool_executor import JournalToolExecutor


class CountingSearch:
    def __init__(self) -> None:
        self.calls = 0
        self.queries = []

    async def search(self, query: str):
        self.calls += 1
        self.queries.append(query)
        return [WebSearchResult("Gin tonic calories", "https://example.com/gin-tonic", "150 kcal per serving")]


async def test_search_web_reuses_normalized_cached_results():
    search = CountingSearch()
    executor = JournalToolExecutor(searxng=search)
    call = ToolCall(id="search", name="search_web", arguments='{"query":"Gin  tonic calories"}')

    first = await executor.execute(None, None, call, [])
    second = await executor.execute(None, None, ToolCall(id="search-2", name="search_web", arguments='{"query":" gin tonic CALORIES "}'), [])

    assert first.ok and first.data["cached"] is False
    assert second.ok and second.data["cached"] is True
    assert second.data["results"] == first.data["results"]
    assert search.calls == 1


async def test_search_web_bounds_cached_payloads_and_rejects_oversized_queries():
    class OversizedSearch(CountingSearch):
        async def search(self, query: str):
            self.calls += 1
            return [WebSearchResult("t" * 300, "https://example.com/" + "u" * 1200, "s" * 1200)]

    search = OversizedSearch()
    executor = JournalToolExecutor(searxng=search)
    result = await executor.execute(None, None, ToolCall(id="bounded", name="search_web", arguments='{"query":"gin tonic calories"}'), [])
    too_long = await executor.execute(None, None, ToolCall(id="long", name="search_web", arguments='{"query":"' + "x" * 257 + '"}'), [])

    assert [len(result.data["results"][0][key]) for key in ("title", "url", "snippet")] == [256, 1024, 1024]
    assert too_long.ok is False and too_long.code == "VALIDATION_ERROR"
    assert search.calls == 1


async def test_search_web_normalizes_whitespace_before_the_outbound_request():
    search = CountingSearch()
    executor = JournalToolExecutor(searxng=search)
    result = await executor.execute(None, None, ToolCall(id="padded", name="search_web", arguments='{"query":"' + " " * 10_000 + "gin   tonic" + " " * 10_000 + '"}'), [])

    assert result.ok and search.queries == ["gin tonic"]
