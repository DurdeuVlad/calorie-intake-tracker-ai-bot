import httpx
import pytest

from app.integrations.openfoodfacts import OpenFoodFactsHttpClient


def _client(handler) -> OpenFoodFactsHttpClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(base_url="https://off.example", transport=transport)
    return OpenFoodFactsHttpClient(settings=None, http=http)  # settings unused when http is provided


@pytest.mark.asyncio
async def test_by_barcode_returns_a_profile_on_a_valid_hit():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/product/5449000000996"
        return httpx.Response(200, json={"status": 1, "product": {"product_name": "Coca-Cola", "nutriments": {"energy-kcal_100g": 42, "proteins_100g": 0, "carbohydrates_100g": 10.6, "fat_100g": 0}}})

    client = _client(handler)
    profile = await client.by_barcode("5449000000996")
    assert profile is not None
    assert profile.name == "Coca-Cola"
    assert profile.calories_per_100g == 42


@pytest.mark.asyncio
async def test_by_barcode_rejects_a_malformed_barcode_without_a_request():
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    client = _client(handler)
    profile = await client.by_barcode("not-a-barcode")
    assert profile is None
    assert called is False


@pytest.mark.asyncio
async def test_by_barcode_returns_none_when_status_is_not_1():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": 0, "product": {}})

    client = _client(handler)
    profile = await client.by_barcode("5449000000996")
    assert profile is None


@pytest.mark.asyncio
async def test_search_by_name_ranks_exact_match_first_and_filters_bad_calories():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "products": [
                    # Listed first in the source, but neither name nor brand matches exactly --
                    # should still rank BEHIND the exact match below despite coming first.
                    {"code": "11111111", "product_name": "Chicken Broth Mix", "brands": "OtherBrand", "nutriments": {"energy-kcal_100g": 50}},
                    {"code": "22222222", "product_name": "Chicken Soup", "brands": "Acme", "nutriments": {"energy-kcal_100g": 45}},
                    {"code": "33333333", "product_name": "Bad Calories Item", "brands": "", "nutriments": {"energy-kcal_100g": 5000}},
                    {"code": "not-a-barcode", "product_name": "Invalid Barcode Item", "brands": "", "nutriments": {"energy-kcal_100g": 50}},
                ]
            },
        )

    client = _client(handler)
    results = await client.search_by_name("Chicken Soup", "Acme")
    assert len(results) == 2
    assert results[0].product_name == "Chicken Soup"  # exact name+brand match wins over partial
    assert results[0].match_quality == "EXACT"
    assert results[1].product_name == "Chicken Broth Mix"
    assert results[1].match_quality == "PARTIAL"


@pytest.mark.asyncio
async def test_search_by_name_returns_empty_on_blank_name():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not make an HTTP call for a blank name")

    client = _client(handler)
    assert await client.search_by_name("", None) == []
