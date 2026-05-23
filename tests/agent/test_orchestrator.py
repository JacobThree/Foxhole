import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from agent.llm.client import LLMResponse, ToolCallRequest
from agent.orchestrator import AgentOrchestrator
from agent.safety import WritePolicy
from agent.settings import AppSettings
from agent.tools.base import ToolResult
from agent.tools.registry import ToolRegistry
from schemas.python.chat import ChatRequest


class DiagnosticArgs(BaseModel):
    service: str


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
        *,
        model_alias: str = "agent-primary",
    ) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                tool_calls=[
                    ToolCallRequest(
                        id="call-1",
                        name="diagnose_service",
                        arguments='{"service": "plex"}',
                    )
                ]
            )
        return LLMResponse(content="Plex is healthy based on the diagnostic tool output.")


def test_orchestrator_runs_tool_calls_through_registry() -> None:
    registry = ToolRegistry()

    @registry.register(
        name="diagnose_service",
        description="Diagnose a service.",
        args_model=DiagnosticArgs,
    )
    def diagnose(arguments: BaseModel) -> ToolResult:
        args = DiagnosticArgs.model_validate(arguments)
        return ToolResult(success=True, data={"service": args.service, "status": "healthy"})

    orchestrator = AgentOrchestrator(
        llm_client=FakeLLM(),
        registry=registry,
        write_policy=WritePolicy(AppSettings()),
    )

    response = asyncio.run(orchestrator.chat(ChatRequest(message="Check plex")))

    assert len(response.tool_traces) == 1
    assert response.tool_traces[0].tool_name == "diagnose_service"
    assert response.budget.tool_call_count == 1
    assert response.findings[0].evidence[0].data["result"]["data"]["service"] == "plex"
    assert "Observed tool output" in response.answer
    assert "Model inference" in response.answer
