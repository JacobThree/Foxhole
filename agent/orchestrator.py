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
from agent.tools.registry import ToolRegistry, default_registry
from schemas.python.chat import ChatRequest, ChatResponse, ToolTrace


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
        store: InMemoryConversationStore | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._registry = registry
        self._write_policy = write_policy
        self._store = store or InMemoryConversationStore()

    async def chat(self, request: ChatRequest, *, caller: str = "api") -> ChatResponse:
        conversation_id, messages = self._store.get_or_create(request.conversation_id)
        messages.append({"role": "user", "content": request.message})
        first = await self._llm_client.complete(messages, self._registry.schemas())
        traces: list[ToolTrace] = []

        if first.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": first.content,
                    "tool_calls": [tool_call.model_dump() for tool_call in first.tool_calls],
                }
            )
            for tool_call in first.tool_calls:
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

            final = await self._llm_client.complete(messages, self._registry.schemas())
            answer = _answer_with_observations(final.content or "", traces)
        else:
            answer = first.content or ""
            messages.append({"role": "assistant", "content": answer})

        return ChatResponse(conversation_id=conversation_id, answer=answer, tool_traces=traces)


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


def create_orchestrator(settings: AppSettings) -> AgentOrchestrator:
    from agent.llm.client import LiteLLMClient

    return AgentOrchestrator(
        llm_client=LiteLLMClient(settings),
        registry=default_registry,
        write_policy=WritePolicy(settings),
    )


def get_orchestrator(settings: AppSettings) -> AgentOrchestrator:
    return create_orchestrator(settings)
