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
from schemas.python.chat import (
    ChatResponse,
    ConfidenceLevel,
    DiagnosticFinding,
    EvidenceItem,
    RiskLevel,
    SuggestedAction,
)


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


def test_chat_response_serializes_evidence_without_breaking_existing_fields() -> None:
    response = ChatResponse(
        conversation_id="conversation-1",
        answer="Plex is CPU-bound during transcodes.",
        findings=[
            DiagnosticFinding(
                title="Plex transcodes are saturated",
                summary="Two sessions are transcoding while CPU is pinned.",
                risk=RiskLevel.MEDIUM,
                confidence=ConfidenceLevel.HIGH,
                evidence=[
                    EvidenceItem(
                        source="plex_inspect_sessions",
                        summary="Active sessions and host load were checked.",
                        data={"plex_token": "secret-token", "cpu_percent": 98},
                    )
                ],
                suggested_actions=[
                    SuggestedAction(
                        title="Restart Plex container",
                        description="Clear the stuck transcode workers.",
                        risk=RiskLevel.HIGH,
                        requires_confirmation=True,
                        confirmation_token="confirm-123",
                    )
                ],
            )
        ],
    )

    body = response.model_dump(mode="json")

    assert body["answer"] == "Plex is CPU-bound during transcodes."
    assert body["tool_traces"] == []
    assert body["findings"][0]["evidence"][0]["data"]["plex_token"] == "********"
    assert "secret-token" not in response.model_dump_json()
