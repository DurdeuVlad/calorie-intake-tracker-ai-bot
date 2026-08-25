"""OpenAI Chat Completions transport, ported from OpenAiJournalAgentModel.java.
Raw HTTP (not the openai SDK) to mirror the Java app's hand-rolled RestClient
call exactly and keep the request/response shape fully under test control."""

import json
from typing import Any

import httpx

from app.agent.system_prompt import instructions
from app.agent.tool_schemas import tool_definitions
from app.config import Settings
from app.db.models.conversation import ConversationMemory
from app.domain.agent_types import AgentContext, AgentExchange, AgentReply, ToolCall


class AgentProviderUnavailableError(RuntimeError):
    pass


class OpenAiJournalAgentModel:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http or httpx.AsyncClient(
            base_url="https://api.openai.com/v1", timeout=httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0)
        )

    async def next(
        self, context: AgentContext, memory: list[ConversationMemory], exchanges: list[AgentExchange]
    ) -> AgentReply | None:
        if not self._settings.openai_api_key:
            return AgentReply(None, [])

        messages: list[dict[str, Any]] = [{"role": "system", "content": instructions(context.romanian)}]
        for turn in memory:
            messages.append({"role": turn.role, "content": turn.content})
        messages.append({"role": "user", "content": context.message})
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
            response = await self._http.post(
                "/chat/completions", headers={"Authorization": f"Bearer {self._settings.openai_api_key}"}, json=body
            )
            response.raise_for_status()
            payload = response.json()
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
