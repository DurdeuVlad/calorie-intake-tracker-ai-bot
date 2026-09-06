"""OpenAI Chat Completions transport with an explicit, testable model boundary."""

import json
from typing import Any

import httpx

from app.agent.system_prompt import instructions
from app.agent.tool_schemas import tool_definitions
from app.config import Settings
from app.db.models.conversation import ConversationMemory
from app.domain.agent_types import AgentContext, AgentExchange, AgentReply, ToolCall
from app.integrations.http_response import request_bounded_json


class AgentProviderUnavailableError(RuntimeError):
    pass


def _replace_server_media_value(message: str, value: str, note: str) -> tuple[str, bool]:
    """Replace the worker-injected media value with one labelled server note.

    The inbox worker currently includes the extracted value in ``message`` so
    the deterministic tools and conversation memory see the same text as the
    model. Replace only a leading value, which is the worker's contract, so an
    incidental mention in user-authored text is never relabelled.
    """
    if not value or not message.startswith(value):
        return message, False
    return f"{note}{message[len(value):]}", True


def _user_content(context: AgentContext) -> str:
    """Build model content with media-derived values labelled exactly once."""
    message = context.message
    media_text = (context.media_text or "").strip()
    media_caption = (context.media_caption or "").strip()

    if context.media_kind == "voice" and media_text:
        message, replaced = _replace_server_media_value(
            message, media_text, f"[Server transcript: {media_text[:500]}]"
        )
        if not replaced:
            message = f"{message}\n[Server transcript: {media_text[:500]}]"
        if media_caption and media_caption not in message:
            message = f"{message}\n[Voice caption: {media_caption[:180]}]"
    elif context.media_kind == "voice_caption_only" and media_caption:
        message, replaced = _replace_server_media_value(
            message, media_caption, f"[Voice caption (no transcript): {media_caption[:180]}]"
        )
        if not replaced:
            message = f"{message}\n[Voice caption (no transcript): {media_caption[:180]}]"
    elif context.media_kind == "photo" and media_text:
        message, replaced = _replace_server_media_value(
            message, media_text, f"[Photo interpretation: {media_text[:500]}]"
        )
        if not replaced:
            message = f"{message}\n[Photo interpretation: {media_text[:500]}]"

    return message


class OpenAiJournalAgentModel:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http or httpx.AsyncClient(
            base_url=settings.openai_base_url, timeout=httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0)
        )

    async def next(
        self, context: AgentContext, memory: list[ConversationMemory], exchanges: list[AgentExchange]
    ) -> AgentReply | None:
        if not self._settings.openai_api_key:
            return AgentReply(None, [])

        messages: list[dict[str, Any]] = [{"role": "system", "content": instructions()}]
        for turn in memory:
            messages.append({"role": turn.role, "content": turn.content})
        messages.append({"role": "user", "content": _user_content(context)})
        for exchange in exchanges:
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": exchange.call.id,
                            "type": "function",
                            "function": {"name": exchange.call.name, "arguments": exchange.call.arguments},
                        }
                    ],
                }
            )
            messages.append({"role": "tool", "tool_call_id": exchange.call.id, "content": self._result_json(exchange)})

        body = {
            "model": self._settings.openai_model,
            "messages": messages,
            "tools": tool_definitions(),
            "tool_choice": "auto",
        }
        try:
            payload = await request_bounded_json(
                self._http,
                "POST",
                "/chat/completions",
                headers={"Authorization": f"Bearer {self._settings.openai_api_key}"},
                json=body,
            )
            message = payload["choices"][0]["message"]
            calls = [
                ToolCall(
                    id=call["id"],
                    name=call["function"]["name"],
                    arguments=call["function"].get("arguments") or "{}",
                )
                for call in (message.get("tool_calls") or [])
            ]
            return AgentReply(message.get("content"), calls)
        except Exception as failure:
            raise AgentProviderUnavailableError("Agent provider unavailable") from failure

    @staticmethod
    def _result_json(exchange: AgentExchange) -> str:
        try:
            return json.dumps(exchange.result.to_json_dict())
        except Exception:  # noqa: BLE001
            return '{"ok":false,"code":"TEMPORARY_FAILURE","data":{},"userHint":null}'

    async def close(self) -> None:
        await self._http.aclose()
