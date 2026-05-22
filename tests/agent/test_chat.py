from collections.abc import Mapping, Sequence
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from agent.llm.client import LLMResponse
from agent.main import app, get_chat_orchestrator
from agent.orchestrator import AgentOrchestrator
from agent.safety import WritePolicy
from agent.settings import AppSettings, get_settings
from agent.tools.registry import ToolRegistry


class StaticLLM:
    async def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
        *,
        model_alias: str = "agent-primary",
    ) -> LLMResponse:
        return LLMResponse(content="No tool call needed.")


def _settings() -> AppSettings:
    return AppSettings(api_bearer_token=SecretStr("test-token"))


def _orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(
        llm_client=StaticLLM(),
        registry=ToolRegistry(),
        write_policy=WritePolicy(_settings()),
    )


def test_chat_requires_auth_and_returns_answer() -> None:
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[get_chat_orchestrator] = _orchestrator
    client = TestClient(app)

    missing = client.post("/chat", json={"message": "hello"})
    ok = client.post(
        "/chat",
        json={"message": "hello"},
        headers={"Authorization": "Bearer test-token"},
    )

    app.dependency_overrides.clear()
    assert missing.status_code == 401
    assert ok.status_code == 200
    assert ok.json()["answer"] == "No tool call needed."
