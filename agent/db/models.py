from __future__ import annotations

from sqlmodel import Field, SQLModel


class EventRecord(SQLModel, table=True):
    __tablename__ = "events"

    id: str = Field(primary_key=True)
    timestamp: str = Field(index=True)
    type: str
    severity: str
    source: str = Field(index=True)
    payload_summary: str
    correlation_id: str | None = Field(default=None, index=True)
    data_json: str
    findings_json: str
    budget_json: str | None = None


class CheckResultRecord(SQLModel, table=True):
    __tablename__ = "check_results"

    id: str = Field(primary_key=True)
    timestamp: str = Field(index=True)
    check_name: str
    source: str
    status: str
    severity: str
    summary: str
    evidence_json: str
    findings_json: str
    suggested_actions_json: str
    duration_ms: float
    skipped_reason: str | None = None
    correlation_id: str = Field(index=True)


class AuditRecord(SQLModel, table=True):
    __tablename__ = "audit_records"

    id: str = Field(primary_key=True)
    timestamp: str = Field(index=True)
    tool_name: str
    caller: str
    arguments_json: str
    safety: str
    confirmation_status: str
    result: str
    result_data_json: str | None = None


class IncidentRecord(SQLModel, table=True):
    __tablename__ = "incidents"

    id: str = Field(primary_key=True)
    created_at: str
    updated_at: str = Field(index=True)
    source: str = Field(index=True)
    title: str
    severity: str
    status: str
    correlation_id: str | None = None
    pinned: bool = False
