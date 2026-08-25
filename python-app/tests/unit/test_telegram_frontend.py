import pytest
from aiogram.exceptions import TelegramBadRequest

from app.messaging.telegram_frontend import TelegramFrontend


class _StubSettings:
    telegram_bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


class _FakeMethod:
    """Stands in for the aiogram TelegramMethod TelegramBadRequest wraps; only
    used to construct the exception, its content is never inspected."""


class _FakeBot:
    def __init__(self, error_message: str | None = None) -> None:
        self.error_message = error_message
        self.calls: list[tuple[int, int, str]] = []

    async def edit_message_text(self, *, chat_id: int, message_id: int, text: str) -> None:
        self.calls.append((chat_id, message_id, text))
        if self.error_message is not None:
            raise TelegramBadRequest(_FakeMethod(), self.error_message)


def _frontend_with_fake_bot(error_message: str | None = None) -> tuple[TelegramFrontend, _FakeBot]:
    frontend = TelegramFrontend(_StubSettings())
    fake_bot = _FakeBot(error_message)
    frontend._bot = fake_bot  # injecting a fake transport for the test
    return frontend, fake_bot


@pytest.mark.asyncio
async def test_edit_succeeds_normally_when_telegram_accepts_the_change():
    frontend, fake_bot = _frontend_with_fake_bot(error_message=None)
    await frontend.edit("123", "456", "new text")
    assert fake_bot.calls == [(123, 456, "new text")]


@pytest.mark.asyncio
async def test_edit_swallows_the_benign_message_is_not_modified_error():
    """Regression test: dispatchers used to log a spurious ERROR and schedule a
    retry for a successful delivery whenever the edited text was already
    displayed -- Telegram treats that as a Bad Request, not a delivery
    failure."""
    frontend, fake_bot = _frontend_with_fake_bot(
        error_message="Bad Request: message is not modified: specified new message content and reply markup are "
        "exactly the same as a current content and reply markup of the message"
    )
    await frontend.edit("123", "456", "same text")  # must not raise
    assert fake_bot.calls == [(123, 456, "same text")]


@pytest.mark.asyncio
async def test_edit_reraises_other_bad_request_errors():
    frontend, _fake_bot = _frontend_with_fake_bot(error_message="Bad Request: message to edit not found")
    with pytest.raises(TelegramBadRequest):
        await frontend.edit("123", "456", "new text")
