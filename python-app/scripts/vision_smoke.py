"""Opt-in live smoke test for photo understanding.

Run from python-app with OPENAI_API_KEY configured:
    python scripts/vision_smoke.py --case all

The source images are public Wikimedia Commons files and are downloaded only to
memory for this run; no image is written to the repository or logged. This
calls the configured OpenAI model and can incur API cost.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.integrations.openai_vision import (
    MAX_MEDIA_BYTES,
    FoodMediaType,
    OpenAiFoodMediaExtractor,
)


@dataclass(frozen=True)
class SmokeCase:
    name: str
    url: str
    source_page: str
    expected: str


CASES = (
    SmokeCase(
        "plated-meal",
        "https://commons.wikimedia.org/wiki/Special:FilePath/Liat_Portal_for_Foodie_Disorder_-_Grilled_Chicken_with_Roasted_Vegetables.jpg",
        "https://commons.wikimedia.org/wiki/File:Liat_Portal_for_Foodie_Disorder_-_Grilled_Chicken_with_Roasted_Vegetables.jpg",
        "Visual identification of grilled chicken and roasted vegetables, not merely text extraction.",
    ),
    SmokeCase(
        "package-front",
        "https://commons.wikimedia.org/wiki/Special:FilePath/Andrew_and_Starr_Edwards%27_Bitchin%27_Sauce_(Chipotle).jpg",
        "https://commons.wikimedia.org/wiki/File:Andrew_and_Starr_Edwards%27_Bitchin%27_Sauce_(Chipotle).jpg",
        "Packaged-product identification with a question about amount eaten if it is not visible.",
    ),
    SmokeCase(
        "nutrition-label",
        "https://commons.wikimedia.org/wiki/Special:FilePath/Nutrition_facts_2014-03-17_08-47.jpg",
        "https://commons.wikimedia.org/wiki/File:Nutrition_facts_2014-03-17_08-47.jpg",
        "Legible label evidence separated from the amount actually consumed.",
    ),
    SmokeCase(
        "ambiguous-bowl",
        "https://commons.wikimedia.org/wiki/Special:FilePath/Chestnut_and_Mushroom_soup_Central_Bar_%26_Kitchen_Subscription_Rooms_Stroud_Gloucestershire_England.jpg",
        "https://commons.wikimedia.org/wiki/Category:Soup_bowls",
        "A cautious dish interpretation and a specific follow-up only if portion or ingredients are material.",
    ),
)


async def _download(client: httpx.AsyncClient, case: SmokeCase) -> bytes:
    response = await client.get(case.url)
    response.raise_for_status()
    data = response.content
    if not data or len(data) > MAX_MEDIA_BYTES:
        raise RuntimeError(f"{case.name}: source image is empty or exceeds the media limit")
    return data


async def main(selected: str) -> None:
    settings = Settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is not configured; no live vision request was made.")

    requested = CASES if selected == "all" else tuple(case for case in CASES if case.name == selected)
    if not requested:
        raise SystemExit(f"Unknown case: {selected}")

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as downloader:
        extractor = OpenAiFoodMediaExtractor(settings)
        try:
            for case in requested:
                data = await _download(downloader, case)
                result = await extractor.extract(data, "image/jpeg", FoodMediaType.PHOTO)
                print(f"[{case.name}] expected: {case.expected}")
                print(f"[{case.name}] source: {case.source_page}")
                print(result)
        finally:
            await extractor.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run live OpenAI food-photo smoke cases (opt-in).")
    parser.add_argument("--case", choices=[case.name for case in CASES] + ["all"], default="all")
    asyncio.run(main(parser.parse_args().case))
