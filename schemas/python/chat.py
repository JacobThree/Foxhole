from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from agent.tools.base import ToolResult

SENSITIVE_DATA_KEYS = ("api_key", "authorization", "bearer", "password", "secret", "token")


def redact_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if any(marker in key.lower() for marker in SENSITIVE_DATA_KEYS):
                redacted[key] = "********"
            else:
                redacted[key] = redact_sensitive_values(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]
    return value


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceItem(BaseModel):
    source: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("data", mode="before")
    @classmethod
    def redact_data(cls, value: Any) -> Any:
        return redact_sensitive_values(value or {})


class SuggestedAction(BaseModel):
    title: str
    description: str
    risk: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    confirmation_token: str | None = None


class DiagnosticFinding(BaseModel):
    title: str
    summary: str
    risk: RiskLevel = RiskLevel.LOW
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    evidence: list[EvidenceItem] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)


class AgentBudgetMetadata(BaseModel):
    model_alias: str = "agent-primary"
    tool_call_count: int = Field(default=0, ge=0)
    max_tool_calls: int | None = Field(default=None, ge=1)
    token_budget: int | None = Field(default=None, ge=1)
    estimated_tokens_used: int | None = Field(default=None, ge=0)


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
    findings: list[DiagnosticFinding] = Field(default_factory=list)
    budget: AgentBudgetMetadata = Field(default_factory=AgentBudgetMetadata)
