from datetime import UTC, datetime, timedelta

import pytest

from app.integrations.openfoodfacts_types import (
    NutritionProfile,
    OpenFoodFactsUnavailable,
    PackagedFoodResult,
)
from app.services import openfoodfacts_cache as cache


class _Session:
    def __init__(self) -> None:
        self.rows = {}

    def add(self, row) -> None:
        self.rows[row.cache_key] = row


class _Off:
    def __init__(self, result=None, error=None, barcode_result=None) -> None:
        self.result = result if result is not None else []
        self.barcode_result = barcode_result
        self.error = error
        self.calls = 0

    async def search_by_name(self, name, brand):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result

    async def by_barcode(self, barcode):
        self.calls += 1
        if self.error:
            raise self.error
        return self.barcode_result


@pytest.fixture
def memory_repo(monkeypatch):
    async def find(session, key):
        return session.rows.get(key)

    async def upsert(session, key, kind, status, payload, fetched_at, expires_at):
        row = session.rows.get(key)
        if row is None:
            row = type(
                "CacheRow",
                (),
                {
                    "cache_key": key,
                    "lookup_kind": kind,
                    "status": status,
                    "payload": payload,
                    "fetched_at": fetched_at,
                    "expires_at": expires_at,
                },
            )()
            session.rows[key] = row
        else:
            row.lookup_kind = kind
            row.status = status
            row.payload = payload
            row.fetched_at = fetched_at
            row.expires_at = expires_at
        return True

    monkeypatch.setattr(cache.openfoodfacts_lookup_cache_repo, "find", find)
    monkeypatch.setattr(cache.openfoodfacts_lookup_cache_repo, "upsert", upsert)


def _result():
    return [PackagedFoodResult("Cola", "Acme", 42, "5941234567890", "https://world.openfoodfacts.org/product/5941234567890", "EXACT")]


def test_cache_keys_preserve_non_latin_food_names():
    assert cache.cache_key("PACKAGED_NAME", "寿司", "") != cache.cache_key("PACKAGED_NAME", "拉面", "")
    assert cache.cache_key("PACKAGED_NAME", "Борщ", "") != cache.cache_key("PACKAGED_NAME", "борщ", "Acme")


@pytest.mark.asyncio
async def test_invalid_provider_products_are_not_persisted_or_served_from_cache(memory_repo):
    invalid = [
        PackagedFoodResult("bad\nproduct", "Acme", 42, "5941234567890", "https://example.com", "EXACT"),
        PackagedFoodResult("Too many calories", None, 10001, "5941234567891", "https://example.com", "PARTIAL"),
    ]
    session, off, now = _Session(), _Off(invalid), datetime.now(UTC)

    result = await cache.packaged_name(session, off, "cola", None, now)

    assert result.status == "NOT_FOUND"
    assert result.value is None
    assert session.rows[cache.cache_key("PACKAGED_NAME", "cola", "")].payload is None


@pytest.mark.asyncio
async def test_invalid_barcode_profile_is_not_cached(memory_repo):
    profile = NutritionProfile(
        name="x" * 256,
        calories_per_100g=42,
        protein_per_100g=None,
        carbs_per_100g=None,
        fat_per_100g=None,
        source="open_food_facts",
        source_url="https://example.com",
    )
    session, off, now = _Session(), _Off(barcode_result=profile), datetime.now(UTC)

    result = await cache.barcode(session, off, "5449000000996", now)

    assert result.status == "NOT_FOUND"
    assert result.value is None
    assert session.rows[cache.cache_key("BARCODE", "5449000000996")].payload is None


@pytest.mark.asyncio
async def test_packaged_cache_miss_calls_provider_then_hit_does_not(memory_repo):
    session, off, now = _Session(), _Off(_result()), datetime.now(UTC)

    first = await cache.packaged_name(session, off, "Cola", "Acme", now)
    second = await cache.packaged_name(session, off, "COLA", "acme", now + timedelta(minutes=1))

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert off.calls == 1
    assert second.source_fetched_at == now


@pytest.mark.asyncio
async def test_expired_cache_refreshes_from_provider(memory_repo):
    session, off, now = _Session(), _Off(_result()), datetime.now(UTC)
    await cache.packaged_name(session, off, "Cola", None, now)
    key = cache.cache_key("PACKAGED_NAME", "Cola", "")
    session.rows[key].expires_at = now - timedelta(seconds=1)

    refreshed = await cache.packaged_name(session, off, "Cola", None, now + timedelta(seconds=1))

    assert refreshed.cache_hit is False
    assert off.calls == 2
    assert session.rows[key].fetched_at == now + timedelta(seconds=1)


@pytest.mark.asyncio
async def test_negative_result_is_cached(memory_repo):
    session, off, now = _Session(), _Off([]), datetime.now(UTC)

    first = await cache.packaged_name(session, off, "unknown food", None, now)
    second = await cache.packaged_name(session, off, "unknown food", None, now + timedelta(minutes=1))

    assert first.status == "NOT_FOUND"
    assert second.status == "NOT_FOUND"
    assert second.cache_hit is True
    assert off.calls == 1


@pytest.mark.asyncio
async def test_rate_limit_is_short_cached_and_does_not_retry_immediately(memory_repo):
    session = _Session()
    off = _Off(error=OpenFoodFactsUnavailable("slow down", rate_limited=True))
    now = datetime.now(UTC)

    first = await cache.packaged_name(session, off, "Cola", None, now)
    second = await cache.packaged_name(session, off, "Cola", None, now + timedelta(minutes=1))

    assert first.status == "RATE_LIMITED"
    assert second.cache_hit is True
    assert second.status == "RATE_LIMITED"
    assert off.calls == 1


@pytest.mark.asyncio
async def test_rate_limit_serves_stale_success_without_hammering_provider(memory_repo):
    session, now = _Session(), datetime.now(UTC)
    healthy = _Off(_result())
    await cache.packaged_name(session, healthy, "Cola", None, now)
    key = cache.cache_key("PACKAGED_NAME", "Cola", "")
    session.rows[key].expires_at = now - timedelta(seconds=1)
    limited = _Off(error=OpenFoodFactsUnavailable("slow down", rate_limited=True))

    stale = await cache.packaged_name(session, limited, "Cola", None, now + timedelta(seconds=1))
    later = await cache.packaged_name(session, limited, "Cola", None, now + timedelta(minutes=1))

    assert stale.status == "STALE_PROVIDER_FAILURE"
    assert stale.cache_hit is True
    assert stale.value is None
    assert later.cache_hit is True
    assert later.status == "STALE_PROVIDER_FAILURE"
    assert later.value is None
    assert limited.calls == 1
