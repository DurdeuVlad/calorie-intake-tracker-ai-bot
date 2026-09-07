"""Nutrition tools: resolve, lookup, private_food, packaged_food, web search/fetch, estimate."""

import asyncio
import ipaddress
import socket
import ssl
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import httpcore
import httpx

from app.db.constraints import (
    MAX_BARCODE_CHARS,
    MAX_BASIS_CHARS,
    MAX_CALORIES,
    MAX_CALORIES_PER_100G,
    MAX_REDIRECTS,
    MAX_TEXT_CHARS,
    MAX_URL_CHARS,
    MAX_WEB_SEARCH_CACHE_ENTRIES,
    MAX_WEB_SEARCH_QUERY_CHARS,
    MAX_WEB_SEARCH_RESULTS,
    MAX_WEB_SEARCH_SNIPPET_CHARS,
    MAX_WEB_SEARCH_TITLE_CHARS,
    MAX_WEB_SEARCH_URL_CHARS,
    MIN_CALORIES_PER_100G,
    NUTRITION_QUOTE_TTL,
)
from app.db.models.nutrition import PendingNutritionQuote
from app.domain.agent_types import AgentToolResult
from app.integrations.openfoodfacts_types import NullOpenFoodFactsClient
from app.repositories import pending_nutrition_quote_repo
from app.services import nutrition_resolver, openfoodfacts_cache
from app.tools.shared import (
    WEB_SEARCH_CACHE_TTL,
    ValidationError,
    _bounded_text,
    _derived_calories,
    _meal_item,
    _quantity_number,
    _str,
    _text,
    _valid_calories_per_100g,
    _valid_item,
    _validate_text,
)

HTTP_PORT = 80
HTTPS_PORT = 443
EXTERNAL_URL_TIMEOUT_SECONDS = 5.0
MIN_REDIRECT_STATUS = 300
MAX_REDIRECT_STATUS = 400


def _provider_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > limit or any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    return value


async def resolve_nutrition(executor, session, context, args, todos) -> AgentToolResult:
    requested = _meal_item(args)
    if not _valid_item(requested):
        return AgentToolResult.failure("VALIDATION_ERROR", "A food name and positive grams are required.")
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

    name = _text(args, "name", MAX_TEXT_CHARS)
    food = await private_food_repo.find_by_user_and_name_ignore_case(session, context.user, name) if name else None
    if food is None:
        return AgentToolResult.failure("NOT_FOUND", "No household food matches that name.")
    return AgentToolResult.success({"name": food.name, "caloriesPer100g": food.calories_per_100g})


async def search_packaged_food(executor, session, context, args, todos) -> AgentToolResult:
    if isinstance(executor.off, NullOpenFoodFactsClient):
        return AgentToolResult.failure("TEMPORARY_FAILURE", "Packaged-food search is unavailable.")
    name = _text(args, "name", MAX_TEXT_CHARS)
    grams = _quantity_number(args, "grams")
    if not name or not name.strip() or grams is None or grams <= 0:
        return AgentToolResult.failure("VALIDATION_ERROR", "A food name and positive grams are required.")
    batch_id = uuid.uuid4()
    products = []
    now = datetime.now(UTC)
    brand = _text(args, "brand", MAX_TEXT_CHARS)
    lookup = await openfoodfacts_cache.packaged_name(session, executor.off, name, brand, now)
    if lookup.status in {"RATE_LIMITED", "TEMPORARY_FAILURE", "STALE_PROVIDER_FAILURE"}:
        return AgentToolResult.failure("TEMPORARY_FAILURE", "Packaged-food lookup is temporarily unavailable; please retry later.")
    for result in lookup.value or []:
        product_name = _provider_text(result.product_name, MAX_TEXT_CHARS)
        barcode = _provider_text(result.barcode, MAX_BARCODE_CHARS)
        if (
            product_name is None
            or barcode is None
            or isinstance(result.calories_per_100g, bool)
            or not isinstance(result.calories_per_100g, int)
            or not _valid_calories_per_100g(result.calories_per_100g)
        ):
            continue
        provider_brand = _provider_text(result.brand, MAX_TEXT_CHARS)
        source_url = _provider_text(result.source_url, MAX_URL_CHARS)
        total_calories = _derived_calories(grams, result.calories_per_100g)
        if total_calories <= 0 or total_calories > MAX_CALORIES:
            continue
        quote = PendingNutritionQuote(
            quote_id=uuid.uuid4(), batch_id=batch_id, user_id=context.user.id, quote_type="PACKAGED_MATCH",
            product_name=product_name, brand=provider_brand, grams=Decimal(str(grams)),
            calories_per_100g=result.calories_per_100g, barcode=barcode, source_url=source_url,
            source_query=" ".join(part for part in (name.strip(), (brand or "").strip()) if part),
            source_fetched_at=lookup.source_fetched_at, source_cache_hit=lookup.cache_hit,
            created_at=now, expires_at=now + NUTRITION_QUOTE_TTL,
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
        return AgentToolResult.failure("VALIDATION_ERROR", f"An estimate needs a food name, positive grams, and calories per 100 g between {MIN_CALORIES_PER_100G} and {MAX_CALORIES_PER_100G}.")
    total_calories = _derived_calories(item.grams, item.calories_per_100g)
    if total_calories > MAX_CALORIES:
        return AgentToolResult.failure("VALIDATION_ERROR", f"That estimate exceeds the {MAX_CALORIES} kcal journal limit.")
    basis = _text(args, "basis", MAX_BASIS_CHARS) or "AI estimate"
    now = datetime.now(UTC)
    quote = PendingNutritionQuote(
        quote_id=uuid.uuid4(), batch_id=uuid.uuid4(), user_id=context.user.id, quote_type="AI_ESTIMATE",
        product_name=item.name, grams=Decimal(str(item.grams)), calories_per_100g=item.calories_per_100g,
        estimate_basis=basis, created_at=now, expires_at=now + NUTRITION_QUOTE_TTL,
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
    try:
        query = _validate_text(query, "query", MAX_WEB_SEARCH_QUERY_CHARS)
    except ValidationError as failure:
        return AgentToolResult.failure("VALIDATION_ERROR", str(failure))
    cache_key = query.lower()
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
        for r in results[:MAX_WEB_SEARCH_RESULTS]
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


def _parse_external_url(url: str) -> httpx.URL | None:
    try:
        parsed = httpx.URL(url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.host:
            return None
        if parsed.port not in (None, HTTP_PORT, HTTPS_PORT):
            return None
        if parsed.username or parsed.password:
            return None
        try:
            ipaddress.ip_address(parsed.host)
        except ValueError:
            if parsed.host.lower().rstrip(".") == "localhost":
                return None
        else:
            # Browserless is configured with hostname allow-listing; reject
            # every raw IP literal here so both boundaries enforce one policy.
            return None
        return parsed
    except (TypeError, ValueError, httpx.InvalidURL):
        return None


def _public_addresses(host: str) -> tuple[str, ...] | None:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return None
    if not infos:
        return None
    addresses: list[str] = []
    try:
        for info in infos:
            address = str(ipaddress.ip_address(info[4][0]))
            if not ipaddress.ip_address(address).is_global:
                return None
            if address not in addresses:
                addresses.append(address)
    except (IndexError, ValueError):
        return None
    return tuple(addresses) or None


def _host_resolves_public(host: str) -> bool:
    return _public_addresses(host) is not None


def _is_safe_external_url(url: str) -> bool:
    parsed = _parse_external_url(url)
    return parsed is not None and _host_resolves_public(parsed.host)


async def _public_addresses_async(host: str) -> tuple[str, ...] | None:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_public_addresses, host),
            timeout=EXTERNAL_URL_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return None


class _PinnedDnsBackend(httpcore.AsyncNetworkBackend):
    """Connect to the address validated for one request, not a fresh DNS result."""

    def __init__(self, hostname: str, address: str) -> None:
        self._hostname = hostname.casefold()
        self._address = address
        self._backend = httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host.casefold() != self._hostname:
            raise OSError("request hostname does not match the validated hostname")
        return await self._backend.connect_tcp(self._address, port, timeout, local_address, socket_options)

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        return await self._backend.connect_unix_socket(path, timeout, socket_options)

    async def sleep(self, seconds=0):
        await self._backend.sleep(seconds)


class _PinnedDnsTransport(httpx.AsyncHTTPTransport):
    """HTTPX transport with a per-request DNS-pinned httpcore backend."""

    def __init__(self, hostname: str, address: str) -> None:
        super().__init__(verify=True, proxy=None, trust_env=False)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            max_connections=1,
            max_keepalive_connections=0,
            keepalive_expiry=0,
            network_backend=_PinnedDnsBackend(hostname, address),
        )


async def _request_with_pinned_dns(url: str, address: str) -> tuple[int, str | None] | None:
    parsed = _parse_external_url(url)
    if parsed is None:
        return None
    transport = _PinnedDnsTransport(parsed.host, address)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            timeout=EXTERNAL_URL_TIMEOUT_SECONDS,
            trust_env=False,
        ) as client, client.stream("GET", url) as response:
            return response.status_code, response.headers.get("location")
    except Exception:  # noqa: BLE001
        return None


async def _is_safe_external_url_async(url: str) -> bool:
    parsed = _parse_external_url(url)
    return parsed is not None and await _public_addresses_async(parsed.host) is not None


async def _resolve_safe_final_url(url: str) -> str | None:
    current = url
    for _hop in range(MAX_REDIRECTS + 1):
        if len(current) > MAX_URL_CHARS:
            return None
        parsed = _parse_external_url(current)
        if parsed is None:
            return None
        addresses = await _public_addresses_async(parsed.host)
        if not addresses:
            return None
        response = await _request_with_pinned_dns(current, addresses[0])
        if response is None:
            return None
        status_code, location = response
        if not (MIN_REDIRECT_STATUS <= status_code < MAX_REDIRECT_STATUS):
            return current
        if not location:
            return None
        try:
            current = str(httpx.URL(current).join(location))
        except (ValueError, httpx.InvalidURL):
            return None
        if len(current) > MAX_URL_CHARS:
            return None
    return None


async def fetch_web_page(executor, session, context, args, todos) -> AgentToolResult:
    if executor.browserless is None:
        return AgentToolResult.failure("TEMPORARY_FAILURE", "Web page fetch is unavailable.")
    url = _text(args, "url", MAX_URL_CHARS)
    if not url:
        return AgentToolResult.failure("VALIDATION_ERROR", "A url is required.")
    resolved = await _resolve_safe_final_url(url)
    parsed = _parse_external_url(resolved) if resolved is not None else None
    if parsed is None or not await _is_safe_external_url_async(resolved):
        return AgentToolResult.failure("VALIDATION_ERROR", "That url cannot be fetched.")
    text = await executor.browserless.fetch_text(resolved, allowed_domain=parsed.host)
    if text is None:
        return AgentToolResult.failure("NOT_FOUND", "That page could not be fetched.")
    return AgentToolResult.success({"url": resolved, "text": text})
