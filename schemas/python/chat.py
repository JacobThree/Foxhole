from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent.tools.base import ToolResult


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    confirmation_tokens: dict[str, str] = Field(default_factory=dict)


class ToolTrace(BaseModel):
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    result: ToolResult


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    tool_traces: list[ToolTrace] = Field(default_factory=list)
