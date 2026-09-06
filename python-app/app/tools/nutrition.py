"""Nutrition tools: resolve, lookup, private_food, packaged_food, web search/fetch, estimate."""

import socket
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx

from app.db.models.nutrition import PendingNutritionQuote
from app.domain.agent_types import AgentToolResult
from app.integrations.openfoodfacts_types import NullOpenFoodFactsClient
from app.repositories import pending_nutrition_quote_repo
from app.services import nutrition_resolver, openfoodfacts_cache
from app.tools.shared import (
    MAX_REDIRECTS,
    MAX_WEB_SEARCH_CACHE_ENTRIES,
    MAX_WEB_SEARCH_QUERY_CHARS,
    MAX_WEB_SEARCH_SNIPPET_CHARS,
    MAX_WEB_SEARCH_TITLE_CHARS,
    MAX_WEB_SEARCH_URL_CHARS,
    WEB_SEARCH_CACHE_TTL,
    _bounded_text,
    _decimal_number,
    _meal_item,
    _str,
    _valid_calories_per_100g,
    _valid_item,
)


async def resolve_nutrition(executor, session, context, args, todos) -> AgentToolResult:
    requested = _meal_item(args)
    resolved = await nutrition_resolver.resolve(session, context.user, requested, executor.off)
    item = resolved.item
    if item is None or item.total_calories is None:
        return AgentToolResult.failure("NOT_FOUND", "Nutrition could not be resolved; search packaged food or estimate it.")
    return AgentToolResult.success(
        {
            "name": item.name,
            "grams": item.grams,
            "totalCalories": item.total_calories,
            "caloriesPer100g": item.calories_per_100g if item.calories_per_100g is not None else "unknown",
            "source": resolved.source,
        }
    )


async def get_private_food(executor, session, context, args, todos) -> AgentToolResult:
    from app.repositories import private_food_repo

    name = _str(args, "name")
    food = await private_food_repo.find_by_user_and_name_ignore_case(session, context.user, name) if name else None
    if food is None:
        return AgentToolResult.failure("NOT_FOUND", "No household food matches that name.")
    return AgentToolResult.success({"name": food.name, "caloriesPer100g": food.calories_per_100g})


async def search_packaged_food(executor, session, context, args, todos) -> AgentToolResult:
    if isinstance(executor.off, NullOpenFoodFactsClient):
        return AgentToolResult.failure("TEMPORARY_FAILURE", "Packaged-food search is unavailable.")
    name = _str(args, "name")
    grams = _decimal_number(args, "grams")
    if not name or grams is None or grams <= 0:
        return AgentToolResult.failure("VALIDATION_ERROR", "A food name and positive grams are required.")
    batch_id = uuid.uuid4()
    products = []
    now = datetime.now(UTC)
    lookup = await openfoodfacts_cache.packaged_name(session, executor.off, name, _str(args, "brand"), now)
    if lookup.status in {"RATE_LIMITED", "TEMPORARY_FAILURE"}:
        return AgentToolResult.failure("TEMPORARY_FAILURE", "Packaged-food lookup is temporarily unavailable; please retry later.")
    for result in lookup.value or []:
        quote = PendingNutritionQuote(
            quote_id=uuid.uuid4(), batch_id=batch_id, user_id=context.user.id, quote_type="PACKAGED_MATCH",
            product_name=result.product_name, brand=result.brand, grams=Decimal(str(grams)),
            calories_per_100g=result.calories_per_100g, barcode=result.barcode, source_url=result.source_url,
            source_query=" ".join(part for part in (name.strip(), (_str(args, "brand") or "").strip()) if part),
            source_fetched_at=lookup.source_fetched_at, source_cache_hit=lookup.cache_hit,
            created_at=now, expires_at=now + timedelta(minutes=30),
        )
        session.add(quote)
        await session.flush()
        products.append(executor._quote_summary(quote))
    if not products:
        return AgentToolResult.failure("NOT_FOUND", "No usable packaged-food result was found.")
    return AgentToolResult.success({"products": products})


async def get_pending_nutrition_quotes(executor, session, context, args, todos) -> AgentToolResult:
    now = datetime.now(UTC)
    first = await pending_nutrition_quote_repo.find_first_by_type(session, context.user, "PACKAGED_MATCH", now)
    if first is None:
        return AgentToolResult.failure("NOT_FOUND", "There are no pending nutrition choices.")
    batch = await pending_nutrition_quote_repo.find_by_batch(session, context.user, first.batch_id, now)
    rows = [executor._quote_summary(q) for q in batch]
    if not rows:
        return AgentToolResult.failure("NOT_FOUND", "There are no pending nutrition choices.")
    return AgentToolResult.success({"quotes": rows})


async def select_packaged_food(executor, session, context, args, todos) -> AgentToolResult:
    from app.tools.shared import _quote_id

    quote = await executor._owned_quote(session, context, _quote_id(args), "PACKAGED_MATCH")
    if quote is None:
        return AgentToolResult.failure("NOT_FOUND", "That packaged-food choice is unavailable or expired.")
    return AgentToolResult.success({"quoteId": str(quote.quote_id), "item": executor._item_summary(executor._quote_item(quote), "open_food_facts", "high"), "source": "Open Food Facts", "evidenceClaim": "verified_source"})


async def estimate_food(executor, session, context, args, todos) -> AgentToolResult:
    item = _meal_item(args)
    if not _valid_item(item) or not _valid_calories_per_100g(item.calories_per_100g):
        return AgentToolResult.failure("VALIDATION_ERROR", "An estimate needs a food name, positive grams, and calories per 100 g between 1 and 10000.")
    basis = _str(args, "basis") or "AI estimate"
    now = datetime.now(UTC)
    quote = PendingNutritionQuote(
        quote_id=uuid.uuid4(), batch_id=uuid.uuid4(), user_id=context.user.id, quote_type="AI_ESTIMATE",
        product_name=item.name, grams=Decimal(str(item.grams)), calories_per_100g=item.calories_per_100g,
        estimate_basis=basis, created_at=now, expires_at=now + timedelta(minutes=30),
    )
    session.add(quote)
    await session.flush()
    return AgentToolResult.success({"quoteId": str(quote.quote_id), "item": executor._item_summary(executor._quote_item(quote), "ai_estimate", "estimate"), "basis": basis})


async def search_web(executor, session, context, args, todos) -> AgentToolResult:
    if executor.searxng is None:
        return AgentToolResult.failure("TEMPORARY_FAILURE", "Web search is unavailable.")
    raw_query = _str(args, "query")
    if not raw_query:
        return AgentToolResult.failure("VALIDATION_ERROR", "A search query is required.")
    query = " ".join(raw_query.split())
    if not query:
        return AgentToolResult.failure("VALIDATION_ERROR", "A search query is required.")
    cache_key = query.lower()
    if len(cache_key) > MAX_WEB_SEARCH_QUERY_CHARS:
        return AgentToolResult.failure("VALIDATION_ERROR", "The search query is too long.")
    now = datetime.now(UTC)
    cached = executor._web_search_cache.get(cache_key)
    if cached is not None and cached[0] > now - WEB_SEARCH_CACHE_TTL:
        return AgentToolResult.success({"results": cached[1], "cached": True})

    results = await executor.searxng.search(query)
    if not results:
        return AgentToolResult.failure("NOT_FOUND", "No web results were found.")
    grounded = [
        {
            "title": _bounded_text(r.title, MAX_WEB_SEARCH_TITLE_CHARS),
            "url": _bounded_text(r.url, MAX_WEB_SEARCH_URL_CHARS),
            "snippet": _bounded_text(r.snippet, MAX_WEB_SEARCH_SNIPPET_CHARS),
        }
        for r in results[:5]
    ]
    if len(executor._web_search_cache) >= MAX_WEB_SEARCH_CACHE_ENTRIES:
        expired = [key for key, (cached_at, _) in executor._web_search_cache.items() if cached_at <= now - WEB_SEARCH_CACHE_TTL]
        for key in expired:
            executor._web_search_cache.pop(key, None)
        if len(executor._web_search_cache) >= MAX_WEB_SEARCH_CACHE_ENTRIES:
            oldest_key = min(executor._web_search_cache, key=lambda key: executor._web_search_cache[key][0])
            executor._web_search_cache.pop(oldest_key, None)
    executor._web_search_cache[cache_key] = (now, grounded)
    return AgentToolResult.success({"results": grounded, "cached": False})


def _is_safe_external_url(url: str) -> bool:
    try:
        parsed = httpx.URL(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return False
        host = parsed.host
        if not host:
            return False
        infos = socket.getaddrinfo(host, None)
        import ipaddress

        for info in infos:
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_unspecified:
                return False
        return True
    except Exception:  # noqa: BLE001
        return False


async def _resolve_safe_final_url(url: str) -> str | None:
    current = url
    async with httpx.AsyncClient(follow_redirects=False, timeout=5.0) as client:
        for _hop in range(MAX_REDIRECTS + 1):
            if not _is_safe_external_url(current):
                return None
            try:
                response = await client.get(current)
            except Exception:  # noqa: BLE001
                return None
            if not (300 <= response.status_code < 400):
                return current
            location = response.headers.get("location")
            if not location:
                return None
            current = str(httpx.URL(current).join(location))
    return None


async def fetch_web_page(executor, session, context, args, todos) -> AgentToolResult:
    if executor.browserless is None:
        return AgentToolResult.failure("TEMPORARY_FAILURE", "Web page fetch is unavailable.")
    url = _str(args, "url")
    if not url:
        return AgentToolResult.failure("VALIDATION_ERROR", "A url is required.")
    if not _is_safe_external_url(url):
        return AgentToolResult.failure("VALIDATION_ERROR", "That url cannot be fetched.")
    resolved = await _resolve_safe_final_url(url)
    if resolved is None:
        return AgentToolResult.failure("VALIDATION_ERROR", "That url cannot be fetched.")
    text = await executor.browserless.fetch_text(resolved)
    if text is None:
        return AgentToolResult.failure("NOT_FOUND", "That page could not be fetched.")
    return AgentToolResult.success({"url": resolved, "text": text})
