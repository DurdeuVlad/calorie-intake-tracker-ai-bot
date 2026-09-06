"""Registry mapping capability topic names to their markdown doc paths.

Capability docs are server-trusted content (stored as files, not
model-generated), so they are not subject to prompt-injection concerns.
The load_instructions tool uses this registry to serve docs to the model."""

from pathlib import Path

_CAPABILITIES_DIR = Path(__file__).parent

TOPICS: dict[str, str] = {
    "nutrition": "nutrition.md",
    "portions": "portions.md",
    "combos": "combos.md",
    "editing": "editing.md",
    "daily_totals": "daily_totals.md",
    "onboarding": "onboarding.md",
    "aliases": "aliases.md",
}


def load(topic: str) -> str | None:
    """Return the markdown content for a topic, or None if the topic is unknown."""
    filename = TOPICS.get(topic)
    if filename is None:
        return None
    path = _CAPABILITIES_DIR / filename
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def valid_topics() -> list[str]:
    return list(TOPICS.keys())
