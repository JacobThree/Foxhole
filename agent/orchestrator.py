from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from typing import Any

from agent.llm.client import LLMClient
from agent.safety import WritePolicy
from agent.settings import AppSettings
from agent.tools.argument_parsing import parse_tool_arguments
from agent.tools.base import ToolResult
from agent.tools.registry import ToolRegistry, default_registry, register_builtin_tools
from schemas.python.chat import (
    AgentBudgetMetadata,
    ChatRequest,
    ChatResponse,
    ConfidenceLevel,
    DiagnosticFinding,
    EvidenceItem,
    RiskLevel,
    SuggestedAction,
    ToolTrace,
)


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[str, list[dict[str, Any]]] = {}

    def get_or_create(self, conversation_id: str | None) -> tuple[str, list[dict[str, Any]]]:
        resolved = conversation_id or str(uuid.uuid4())
        return resolved, self._conversations.setdefault(resolved, [])


class AgentOrchestrator:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        registry: ToolRegistry,
        write_policy: WritePolicy,
        settings: AppSettings | None = None,
        store: InMemoryConversationStore | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._registry = registry
        self._write_policy = write_policy
        self._settings = settings or AppSettings()
        self._store = store or InMemoryConversationStore()

    async def chat(self, request: ChatRequest, *, caller: str = "api") -> ChatResponse:
        conversation_id, messages = self._store.get_or_create(request.conversation_id)
        messages.append({"role": "user", "content": request.message})
        selected_tools = self._registry.list_for_message(request.message)
        selected_schemas = self._registry.schemas(selected_tools)
        selected_tool_names = {tool.name for tool in selected_tools}
        budget = _BudgetTracker(self._settings, tool_schema_count=len(selected_schemas))
        stopped_reason = _token_budget_stop_reason(budget, messages, selected_schemas)
        if stopped_reason is not None:
            return ChatResponse(
                conversation_id=conversation_id,
                answer=stopped_reason,
                budget=budget.metadata(stopped_reason=stopped_reason),
            )

        budget.record_model_request(messages, selected_schemas)
        first = await self._llm_client.complete(messages, selected_schemas)
        budget.record_model_response(first)
        traces: list[ToolTrace] = []

        if first.tool_calls:
            if len(first.tool_calls) > self._settings.agent_max_tool_calls:
                stopped_reason = (
                    "Budget limit reached: the model requested "
                    f"{len(first.tool_calls)} tool calls, but the limit is "
                    f"{self._settings.agent_max_tool_calls}."
                )
                messages.append({"role": "assistant", "content": stopped_reason})
                return ChatResponse(
                    conversation_id=conversation_id,
                    answer=stopped_reason,
                    budget=budget.metadata(stopped_reason=stopped_reason),
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": first.content,
                    "tool_calls": [tool_call.model_dump() for tool_call in first.tool_calls],
                }
            )
            for tool_call in first.tool_calls:
                if tool_call.name not in selected_tool_names:
                    result = ToolResult(
                        success=False,
                        error=f"Tool {tool_call.name} was not loaded for this request intent.",
                    )
                    trace = ToolTrace(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        arguments={},
                        result=result,
                    )
                    traces.append(trace)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": trace.result.model_dump_json(),
                        }
                    )
                    continue

                tool = self._registry.get(tool_call.name)
                arguments = await parse_tool_arguments(tool, tool_call.arguments)
                decision = self._write_policy.evaluate(
                    tool=tool,
                    caller=caller,
                    arguments=arguments,
                    confirmation_token=request.confirmation_tokens.get(tool.name),
                )
                if decision.allowed:
                    result = await tool.run(arguments)
                    if decision.write_action.requested:
                        result.write_action = decision.write_action
                        self._write_policy.record_tool_result(
                            decision.write_action.audit_id,
                            result.data,
                            result.success,
                        )
                else:
                    result = ToolResult(
                        success=False,
                        error=decision.reason,
                        write_action=decision.write_action,
                    )
                trace = ToolTrace(
                    tool_call_id=tool_call.id,
                    tool_name=tool.name,
                    arguments=arguments.model_dump(mode="json"),
                    result=result,
                )
                traces.append(trace)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool.name,
                        "content": trace.result.model_dump_json(),
                    }
                )

            stopped_reason = _model_budget_stop_reason(budget)
            if stopped_reason is not None:
                answer = _answer_with_observations(stopped_reason, traces)
            else:
                stopped_reason = _token_budget_stop_reason(budget, messages, selected_schemas)
                if stopped_reason is not None:
                    answer = _answer_with_observations(stopped_reason, traces)
                else:
                    budget.record_model_request(messages, selected_schemas)
                    final = await self._llm_client.complete(messages, selected_schemas)
                    budget.record_model_response(final)
                    answer = _answer_with_observations(final.content or "", traces)
        else:
            answer = first.content or ""
            messages.append({"role": "assistant", "content": answer})

        return ChatResponse(
            conversation_id=conversation_id,
            answer=answer,
            tool_traces=traces,
            findings=_findings_from_traces(traces),
            budget=budget.metadata(traces=traces, stopped_reason=stopped_reason),
        )


def _answer_with_observations(model_content: str, traces: Sequence[ToolTrace]) -> str:
    observed = [
        {
            "tool": trace.tool_name,
            "success": trace.result.success,
            "data": trace.result.data,
            "error": trace.result.error,
        }
        for trace in traces
    ]
    return (
        "Observed tool output:\n"
        f"{json.dumps(observed, sort_keys=True)}\n\n"
        "Model inference:\n"
        f"{model_content}"
    )


def _findings_from_traces(traces: Sequence[ToolTrace]) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for trace in traces:
        write_action = trace.result.write_action
        suggested_actions: list[SuggestedAction] = []
        if write_action.requested:
            suggested_actions.append(
                SuggestedAction(
                    title=f"Run {trace.tool_name}",
                    description=trace.result.error or "Execute the requested write action.",
                    risk=RiskLevel.HIGH,
                    requires_confirmation=write_action.confirmation_required,
                    confirmation_token=write_action.confirmation_token,
                )
            )

        findings.append(
            DiagnosticFinding(
                title=f"{trace.tool_name} result",
                summary=trace.result.error
                or ("Tool completed successfully." if trace.result.success else "Tool failed."),
                risk=RiskLevel.LOW if trace.result.success else RiskLevel.MEDIUM,
                confidence=ConfidenceLevel.HIGH,
                evidence=[
                    EvidenceItem(
                        source=trace.tool_name,
                        summary="Structured tool result",
                        data={
                            "arguments": trace.arguments,
                            "result": trace.result.model_dump(mode="json"),
                        },
                    )
                ],
                suggested_actions=suggested_actions,
            )
        )
    return findings


class _BudgetTracker:
    def __init__(self, settings: AppSettings, *, tool_schema_count: int) -> None:
        self._settings = settings
        self._tool_schema_count = tool_schema_count
        self.model_call_count = 0
        self.estimated_input_tokens = 0
        self.estimated_output_tokens = 0

    def record_model_request(
        self, messages: Sequence[dict[str, Any]], tools: Sequence[dict[str, Any]]
    ) -> None:
        self.model_call_count += 1
        self.estimated_input_tokens += _estimate_tokens({"messages": messages, "tools": tools})

    def record_model_response(self, response: Any) -> None:
        dumped = response.model_dump(mode="json") if hasattr(response, "model_dump") else response
        self.estimated_output_tokens += _estimate_tokens(dumped)

    def metadata(
        self,
        *,
        traces: Sequence[ToolTrace] = (),
        stopped_reason: str | None = None,
    ) -> AgentBudgetMetadata:
        tokens = self.estimated_input_tokens + self.estimated_output_tokens
        return AgentBudgetMetadata(
            model_alias="agent-primary",
            model_call_count=self.model_call_count,
            max_model_calls=self._settings.agent_max_model_calls,
            tool_call_count=len(traces),
            max_tool_calls=self._settings.agent_max_tool_calls,
            tool_schema_count=self._tool_schema_count,
            log_line_count=sum(trace.result.raw_line_count or 0 for trace in traces),
            token_budget=self._settings.agent_token_budget,
            estimated_tokens_used=tokens,
            estimated_input_tokens=self.estimated_input_tokens,
            estimated_output_tokens=self.estimated_output_tokens,
            estimated_cost_usd=round(
                (tokens / 1000) * self._settings.agent_estimated_cost_per_1k_tokens,
                6,
            ),
            stopped_reason=stopped_reason,
        )


def _model_budget_stop_reason(budget: _BudgetTracker) -> str | None:
    if budget.model_call_count >= budget._settings.agent_max_model_calls:
        return (
            "Budget limit reached: model call limit "
            f"{budget._settings.agent_max_model_calls} reached before final reasoning."
        )
    return None


def _token_budget_stop_reason(
    budget: _BudgetTracker,
    messages: Sequence[dict[str, Any]],
    tools: Sequence[dict[str, Any]],
) -> str | None:
    next_input_tokens = _estimate_tokens({"messages": messages, "tools": tools})
    projected = budget.estimated_input_tokens + budget.estimated_output_tokens + next_input_tokens
    if projected > budget._settings.agent_token_budget:
        return (
            "Budget limit reached: projected context is "
            f"{projected} tokens, above the limit of {budget._settings.agent_token_budget}."
        )
    return None


def _estimate_tokens(value: Any) -> int:
    text = json.dumps(value, default=str, sort_keys=True)
    return max(1, (len(text) + 3) // 4)


def create_orchestrator(settings: AppSettings) -> AgentOrchestrator:
    from agent.llm.client import LiteLLMClient

    register_builtin_tools(default_registry)
    return AgentOrchestrator(
        llm_client=LiteLLMClient(settings),
        registry=default_registry,
        write_policy=WritePolicy(settings),
        settings=settings,
    )


def get_orchestrator(settings: AppSettings) -> AgentOrchestrator:
    return create_orchestrator(settings)
