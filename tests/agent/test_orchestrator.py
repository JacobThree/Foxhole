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


class CaptureToolsLLM:
    def __init__(self) -> None:
        self.tool_names: list[list[str]] = []

    async def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
        *,
        model_alias: str = "agent-primary",
    ) -> LLMResponse:
        self.tool_names.append([tool["function"]["name"] for tool in tools or []])
        return LLMResponse(content="No tool call needed.")


class TooManyToolCallsLLM:
    async def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
        *,
        model_alias: str = "agent-primary",
    ) -> LLMResponse:
        return LLMResponse(
            tool_calls=[
                ToolCallRequest(id="call-1", name="lookup", arguments='{"service": "plex"}'),
                ToolCallRequest(id="call-2", name="lookup", arguments='{"service": "sonarr"}'),
            ]
        )


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


def test_orchestrator_sends_intent_scoped_tool_schemas() -> None:
    registry = ToolRegistry()

    @registry.register(
        name="plex_active_sessions",
        description="Read Plex sessions.",
        args_model=DiagnosticArgs,
    )
    def plex(arguments: BaseModel) -> ToolResult:
        return ToolResult(success=True, data=arguments.model_dump())

    @registry.register(
        name="network_unknown_devices",
        description="Find unknown network devices.",
        args_model=DiagnosticArgs,
    )
    def network(arguments: BaseModel) -> ToolResult:
        return ToolResult(success=True, data=arguments.model_dump())

    llm = CaptureToolsLLM()
    orchestrator = AgentOrchestrator(
        llm_client=llm,
        registry=registry,
        write_policy=WritePolicy(AppSettings()),
    )

    asyncio.run(orchestrator.chat(ChatRequest(message="Why is Plex buffering?")))

    assert llm.tool_names == [["plex_active_sessions"]]


def test_orchestrator_stops_when_tool_call_limit_exceeded() -> None:
    registry = ToolRegistry()

    @registry.register(name="lookup", description="Lookup.", args_model=DiagnosticArgs)
    def lookup(arguments: BaseModel) -> ToolResult:
        return ToolResult(success=True, data=arguments.model_dump())

    orchestrator = AgentOrchestrator(
        llm_client=TooManyToolCallsLLM(),
        registry=registry,
        write_policy=WritePolicy(AppSettings(agent_max_tool_calls=1)),
        settings=AppSettings(agent_max_tool_calls=1),
    )

    response = asyncio.run(orchestrator.chat(ChatRequest(message="What changed?")))

    assert response.tool_traces == []
    assert response.budget.model_call_count == 1
    assert response.budget.tool_call_count == 0
    assert response.budget.stopped_reason is not None
    assert "Budget limit reached" in response.answer
