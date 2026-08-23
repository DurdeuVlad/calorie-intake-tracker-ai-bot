import pytest

from app.services import journal_application_service as service
from app.services.journal_application_service import JournalApplicationService


class _Settings:
    preferred_language = "en"

    def set_preferred_language(self, language):
        self.preferred_language = language


class _Agent:
    context = None

    async def run(self, session, context):
        self.context = context
        return "receipt"


@pytest.mark.asyncio
async def test_media_metadata_reaches_the_agent_without_becoming_user_message(monkeypatch):
    settings = _Settings()

    async def get_settings(session, user_id):
        return settings

    monkeypatch.setattr(service.food_user_repo, "get_settings", get_settings)
    agent = _Agent()
    journal = JournalApplicationService("Europe/Bucharest", agent=agent)
    user = type("User", (), {"id": 1})()

    reply = await journal.handle(
        None,
        user,
        "1",
        "two eggs",
        media_kind="voice",
        media_text="two eggs",
        media_caption="breakfast",
    )

    assert reply == "receipt"
    assert agent.context.message == "two eggs"
    assert agent.context.media_kind == "voice"
    assert agent.context.media_text == "two eggs"
    assert agent.context.media_caption == "breakfast"
