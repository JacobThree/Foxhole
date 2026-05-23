import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from schemas.python.chat import (
    AgentBudgetMetadata,
    DiagnosticFinding,
    EvidenceItem,
    SuggestedAction,
)


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


class CheckStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    FAILED = "failed"
    SKIPPED = "skipped"


class ScheduledCheckResult(BaseModel):
    check: str
    source: str
    status: CheckStatus
    severity: str = "info"
    summary: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    findings: list[DiagnosticFinding] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    duration_ms: float = Field(default=0, ge=0)
    skipped_reason: str | None = None
    correlation_id: str = Field(default_factory=generate_id)


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


class AuditReceipt(BaseModel):
    id: str
    timestamp: str
    tool_name: str
    caller: str
    arguments: dict[str, Any]
    safety: str
    confirmation_status: str
    result: str
    result_data: dict[str, Any] | list[Any] | str | int | float | bool | None = None


class IncidentSummary(BaseModel):
    id: str
    created_at: str
    updated_at: str
    source: str
    title: str
    severity: str
    status: str
    correlation_id: str | None = None
    pinned: bool = False
    event_count: int = 0


class IncidentTimelineEntry(BaseModel):
    timestamp: str
    source: str
    severity: str
    summary: str
    event_id: str | None = None
    audit_id: str | None = None
    evidence_summary: str | None = None
    suggested_action: str | None = None


class IncidentDetail(BaseModel):
    incident: IncidentSummary
    timeline: list[IncidentTimelineEntry] = Field(default_factory=list)
