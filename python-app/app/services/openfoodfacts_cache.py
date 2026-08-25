"""Durable, privacy-conscious cache policy for Open Food Facts responses."""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import OpenFoodFactsLookupCache
from app.integrations.openfoodfacts_types import (
    NutritionProfile,
    OpenFoodFactsClient,
    OpenFoodFactsUnavailable,
    PackagedFoodResult,
)
from app.repositories import openfoodfacts_lookup_cache_repo

SUCCESS_TTL = timedelta(days=30)
NOT_FOUND_TTL = timedelta(hours=12)
RATE_LIMIT_TTL = timedelta(minutes=10)
FAILURE_TTL = timedelta(minutes=2)


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", without_marks.lower()).strip()


def cache_key(kind: str, *values: str) -> str:
    # Never persist the original user terms: only a normalized, one-way digest.
    material = "|".join([kind, *(_normalized(value) for value in values)])
    return hashlib.sha256(material.encode()).hexdigest()


@dataclass(frozen=True)
class CachedLookup:
    value: NutritionProfile | list[PackagedFoodResult] | None
    cache_hit: bool
    source_fetched_at: datetime | None
    status: str


def _profile_payload(value: NutritionProfile) -> str:
    return json.dumps(value.__dict__, separators=(",", ":"), sort_keys=True)


def _profile_from(payload: str) -> NutritionProfile:
    return NutritionProfile(**json.loads(payload))


def _products_payload(values: list[PackagedFoodResult]) -> str:
    return json.dumps([value.__dict__ for value in values], separators=(",", ":"), sort_keys=True)


def _products_from(payload: str) -> list[PackagedFoodResult]:
    return [PackagedFoodResult(**row) for row in json.loads(payload)]


async def _cached_or_fetch(
    session: AsyncSession, key: str, kind: str, now: datetime, fetch, decode
) -> CachedLookup:
    row = await openfoodfacts_lookup_cache_repo.find(session, key)
    if row is not None and row.expires_at > now:
        if row.status == "SUCCESS" and row.payload:
            return CachedLookup(decode(row.payload), True, row.fetched_at, row.status)
        return CachedLookup(None, True, row.fetched_at, row.status)
    try:
        value = await fetch()
        status = "SUCCESS" if value else "NOT_FOUND"
        ttl = SUCCESS_TTL if value else NOT_FOUND_TTL
        payload = None if not value else (_profile_payload(value) if kind == "BARCODE" else _products_payload(value))
    except OpenFoodFactsUnavailable as error:
        status = "RATE_LIMITED" if error.rate_limited else "TEMPORARY_FAILURE"
        ttl = RATE_LIMIT_TTL if error.rate_limited else FAILURE_TTL
        payload = None
        # Expired positive data is safer and more useful than an invented
        # fallback. Mark it stale; callers must not describe it as live.
        if row is not None and row.status == "SUCCESS" and row.payload:
            # Retain the payload and install the short backoff window so a
            # burst of callers cannot hammer a rate-limited provider.
            row.expires_at = now + ttl
            return CachedLookup(decode(row.payload), True, row.fetched_at, "STALE_PROVIDER_FAILURE")
    if row is None:
        session.add(OpenFoodFactsLookupCache(cache_key=key, lookup_kind=kind, status=status, payload=payload, fetched_at=now, expires_at=now + ttl))
    else:
        row.status, row.payload, row.fetched_at, row.expires_at = status, payload, now, now + ttl
    return CachedLookup(value if status == "SUCCESS" else None, False, now, status)


async def barcode(session: AsyncSession, off: OpenFoodFactsClient, barcode_value: str, now: datetime) -> CachedLookup:
    return await _cached_or_fetch(session, cache_key("BARCODE", barcode_value), "BARCODE", now, lambda: off.by_barcode(barcode_value), _profile_from)


async def packaged_name(session: AsyncSession, off: OpenFoodFactsClient, name: str, brand: str | None, now: datetime) -> CachedLookup:
    return await _cached_or_fetch(session, cache_key("PACKAGED_NAME", name, brand or ""), "PACKAGED_NAME", now, lambda: off.search_by_name(name, brand), _products_from)
