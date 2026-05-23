import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from schemas.python.chat import AgentBudgetMetadata, DiagnosticFinding


def get_utc_now() -> str:
    return datetime.now(UTC).isoformat()


def generate_id() -> str:
    return str(uuid.uuid4())


class Event(BaseModel):
    id: str = Field(default_factory=generate_id)
    timestamp: str = Field(default_factory=get_utc_now)
    type: str  # "alert", "tool_call", "confirmation", "write_result"
    severity: str = "info"
    source: str
    payload_summary: str
    correlation_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    findings: list[DiagnosticFinding] = Field(default_factory=list)
    budget: AgentBudgetMetadata | None = None


class IntegrationState(BaseModel):
    name: str
    enabled: bool
    configured: bool
    missing_configuration: list[str] = Field(default_factory=list)


class CheckSummary(BaseModel):
    id: str
    timestamp: str
    source: str
    status: str
    severity: str
    summary: str
    correlation_id: str | None = None


class DashboardSummary(BaseModel):
    readiness: dict[str, bool]
    integrations: list[IntegrationState]
    severity_counts: dict[str, int]
    latest_checks: list[CheckSummary] = Field(default_factory=list)
    recent_events: list[Event] = Field(default_factory=list)


class ToolCapability(BaseModel):
    tool_name: str
    description: str
    safety: str
    stage_behavior: str


class IntegrationCapabilities(BaseModel):
    integration: str
    enabled: bool
    configured: bool
    missing_configuration: list[str] = Field(default_factory=list)
    capabilities: list[ToolCapability] = Field(default_factory=list)
