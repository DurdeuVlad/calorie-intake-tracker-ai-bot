import httpx
import pytest

from app.messaging.inbound_message import AttachmentKind
from app.messaging.mattermost_frontend import MattermostFrontend


class StubSettings:
    mattermost_internal_url = "https://mattermost.example"
    mattermost_bot_token = "bot-token"
    mattermost_bot_user_id = "bot-user"


def _frontend(handler) -> MattermostFrontend:
    # Mirrors the Authorization header the real constructor sets when it builds
    # its own client -- must be added explicitly here since we're injecting a
    # test client (with a mock transport) instead of letting it build one.
    http = httpx.AsyncClient(
        base_url="https://mattermost.example",
        headers={"Authorization": "Bearer bot-token"},
        transport=httpx.MockTransport(handler),
    )
    return MattermostFrontend(StubSettings(), http=http)


@pytest.mark.asyncio
async def test_send_posts_a_message_and_returns_the_post_id():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v4/posts"
        assert request.headers["authorization"] == "Bearer bot-token"
        return httpx.Response(200, json={"id": "post-123"})

    message_id = await _frontend(handler).send("channel-1", "hello")
    assert message_id == "post-123"


@pytest.mark.asyncio
async def test_attachment_classifies_kind_by_mime_type():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"mime_type": "image/png", "name": "photo.png"})

    attachment = await _frontend(handler).attachment("file-1")
    assert attachment.kind == AttachmentKind.PHOTO
    assert attachment.mime_type == "image/png"


@pytest.mark.asyncio
async def test_direct_channel_returns_the_channel_id():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v4/channels/direct"
        return httpx.Response(200, json={"id": "dm-channel-1"})

    channel_id = await _frontend(handler).direct_channel("some-user")
    assert channel_id == "dm-channel-1"
