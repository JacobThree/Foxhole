from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventRecord:
    id: str
    timestamp: str
    type: str
    severity: str
    source: str
    payload_summary: str
    correlation_id: str | None
    data_json: str
    findings_json: str
    budget_json: str | None


@dataclass(frozen=True)
class CheckResultRecord:
    id: str
    timestamp: str
    check: str
    source: str
    status: str
    severity: str
    summary: str
    evidence_json: str
    findings_json: str
    suggested_actions_json: str
    duration_ms: float
    skipped_reason: str | None
    correlation_id: str


@dataclass(frozen=True)
class AuditRecord:
    id: str
    timestamp: str
    tool_name: str
    caller: str
    arguments_json: str
    safety: str
    confirmation_status: str
    result: str
    result_data_json: str | None


@dataclass(frozen=True)
class IncidentRecord:
    id: str
    created_at: str
    updated_at: str
    source: str
    title: str
    severity: str
    status: str
    correlation_id: str | None
    pinned: bool

