"""Durable, privacy-conscious cache policy for Open Food Facts responses."""

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.openfoodfacts_types import (
    NutritionProfile,
    OpenFoodFactsClient,
    OpenFoodFactsUnavailable,
    PackagedFoodResult,
    validate_nutrition_profile,
    validate_packaged_food_result,
)
from app.repositories import openfoodfacts_lookup_cache_repo

SUCCESS_TTL = timedelta(days=30)
NOT_FOUND_TTL = timedelta(hours=12)
RATE_LIMIT_TTL = timedelta(minutes=10)
FAILURE_TTL = timedelta(minutes=2)


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(
        "".join(char.lower() if char.isalnum() else " " for char in without_marks).split()
    )


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
    value = validate_nutrition_profile(value)
    return json.dumps(value.__dict__, separators=(",", ":"), sort_keys=True)


def _profile_from(payload: str) -> NutritionProfile:
    return validate_nutrition_profile(NutritionProfile(**json.loads(payload)))


def _products_payload(values: list[PackagedFoodResult]) -> str:
    values = [validate_packaged_food_result(value) for value in values]
    return json.dumps([value.__dict__ for value in values], separators=(",", ":"), sort_keys=True)


def _products_from(payload: str) -> list[PackagedFoodResult]:
    return [validate_packaged_food_result(PackagedFoodResult(**row)) for row in json.loads(payload)]


def _sanitize_value(value, kind: str):
    if kind == "BARCODE":
        if value is None:
            return None
        try:
            return validate_nutrition_profile(value)
        except (AttributeError, TypeError, ValueError):
            return None
    if not isinstance(value, list):
        return []
    sanitized: list[PackagedFoodResult] = []
    for candidate in value:
        try:
            sanitized.append(validate_packaged_food_result(candidate))
        except (AttributeError, TypeError, ValueError):
            continue
    return sanitized


def _decode_or_invalidate(row, decode, now: datetime):
    try:
        return decode(row.payload)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        row.expires_at = now
        return None


async def _cached_or_fetch(
    session: AsyncSession, key: str, kind: str, now: datetime, fetch, decode
) -> CachedLookup:
    row = await openfoodfacts_lookup_cache_repo.find(session, key)
    if row is not None and row.expires_at > now:
        if row.status == "SUCCESS" and row.payload:
            cached = _decode_or_invalidate(row, decode, now)
            if cached is not None:
                return CachedLookup(cached, True, row.fetched_at, row.status)
        elif row.status != "SUCCESS":
            return CachedLookup(None, True, row.fetched_at, row.status)
    try:
        value = _sanitize_value(await fetch(), kind)
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
            # Retain only validated payloads and install the short backoff
            # window so a burst of callers cannot hammer a rate-limited provider.
            stale = _decode_or_invalidate(row, decode, now)
            if stale is not None:
                row.status = "STALE_PROVIDER_FAILURE"
                row.expires_at = now + ttl
                return CachedLookup(None, True, row.fetched_at, row.status)
    expires_at = now + ttl
    if row is None:
        persisted = await openfoodfacts_lookup_cache_repo.upsert(
            session,
            key,
            kind,
            status,
            payload,
            now,
            expires_at,
        )
        if status != "SUCCESS" and not persisted:
            concurrent = await openfoodfacts_lookup_cache_repo.find(session, key)
            if concurrent is not None and concurrent.expires_at > now:
                if concurrent.status == "SUCCESS" and concurrent.payload:
                    cached = _decode_or_invalidate(concurrent, decode, now)
                    if cached is not None:
                        return CachedLookup(cached, True, concurrent.fetched_at, concurrent.status)
                elif concurrent.status != "SUCCESS":
                    return CachedLookup(None, True, concurrent.fetched_at, concurrent.status)
    else:
        row.status, row.payload, row.fetched_at, row.expires_at = status, payload, now, expires_at
    return CachedLookup(value if status == "SUCCESS" else None, False, now, status)


async def barcode(session: AsyncSession, off: OpenFoodFactsClient, barcode_value: str, now: datetime) -> CachedLookup:
    return await _cached_or_fetch(session, cache_key("BARCODE", barcode_value), "BARCODE", now, lambda: off.by_barcode(barcode_value), _profile_from)


async def packaged_name(session: AsyncSession, off: OpenFoodFactsClient, name: str, brand: str | None, now: datetime) -> CachedLookup:
    return await _cached_or_fetch(session, cache_key("PACKAGED_NAME", name, brand or ""), "PACKAGED_NAME", now, lambda: off.search_by_name(name, brand), _products_from)
