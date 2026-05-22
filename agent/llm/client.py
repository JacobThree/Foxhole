from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, Field, SecretStr

from agent.settings import AppSettings


class ToolCallRequest(BaseModel):
    id: str
    name: str
    arguments: str


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)


class LLMClient(Protocol):
    async def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
        *,
        model_alias: str = "agent-primary",
    ) -> LLMResponse:
        """Return the next assistant response."""


class LiteLLMClient:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    async def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
        *,
        model_alias: str = "agent-primary",
    ) -> LLMResponse:
        import litellm

        model_config = build_router_config(self._settings)[model_alias]
        response = await litellm.acompletion(
            model=model_config["model"],
            messages=list(messages),
            tools=list(tools or []),
            api_base=model_config.get("api_base"),
            api_key=model_config.get("api_key"),
            timeout=model_config["timeout"],
            num_retries=model_config["retries"],
            fallbacks=model_config["fallbacks"],
        )
        choice = response.choices[0].message
        tool_calls = [
            ToolCallRequest(
                id=tool_call.id,
                name=tool_call.function.name,
                arguments=tool_call.function.arguments,
            )
            for tool_call in (choice.tool_calls or [])
        ]
        return LLMResponse(content=choice.content, tool_calls=tool_calls)


def build_router_config(settings: AppSettings) -> dict[str, dict[str, Any]]:
    primary_key = _secret(settings.llm_primary_api_key)
    local_base = settings.llm_local_api_base
    vllm_base = settings.llm_vllm_api_base
    return {
        "agent-primary": {
            "model": settings.llm_primary_model,
            "api_base": settings.llm_primary_api_base,
            "api_key": primary_key,
            "timeout": settings.llm_timeout_seconds,
            "retries": settings.llm_retries,
            "fallbacks": ["agent-local", "agent-vllm"],
        },
        "agent-local": {
            "model": settings.llm_local_model,
            "api_base": local_base,
            "api_key": None,
            "timeout": settings.llm_timeout_seconds,
            "retries": settings.llm_retries,
            "fallbacks": [],
        },
        "agent-vllm": {
            "model": settings.llm_vllm_model,
            "api_base": vllm_base,
            "api_key": None,
            "timeout": settings.llm_timeout_seconds,
            "retries": settings.llm_retries,
            "fallbacks": [],
        },
    }


def _secret(value: SecretStr | None) -> str | None:
    return value.get_secret_value() if value is not None else None
