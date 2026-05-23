from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete
from sqlmodel import col, select

from agent.db.models import AuditRecord, CheckResultRecord, EventRecord, IncidentRecord
from agent.db.session import db_session
from agent.settings import AppSettings, get_settings
from schemas.python.events import (
    AuditReceipt,
    CheckStatus,
    Event,
    IncidentDetail,
    IncidentSummary,
    IncidentTimelineEntry,
    ScheduledCheckResult,
    generate_id,
    get_utc_now,
)


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _json_load(value: str | None, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class EventRepository:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self._settings = settings or get_settings()

    def store_event(self, event: Event) -> None:
        record = EventRecord(
            id=event.id,
            timestamp=event.timestamp,
            type=event.type,
            severity=event.severity,
            source=event.source,
            payload_summary=event.payload_summary,
            correlation_id=event.correlation_id,
            data_json=_json_dump(event.data),
            findings_json=_json_dump(
                [finding.model_dump(mode="json") for finding in event.findings]
            ),
            budget_json=event.budget.model_dump_json() if event.budget else None,
        )
        with db_session(self._settings) as session:
            session.merge(record)

    def store_check_result(self, result: ScheduledCheckResult) -> str:
        check_id = generate_id()
        status = (
            result.status.value if isinstance(result.status, CheckStatus) else str(result.status)
        )
        record = CheckResultRecord(
            id=check_id,
            timestamp=get_utc_now(),
            check_name=result.check,
            source=result.source,
            status=status,
            severity=result.severity,
            summary=result.summary,
            evidence_json=_json_dump([item.model_dump(mode="json") for item in result.evidence]),
            findings_json=_json_dump(
                [item.model_dump(mode="json") for item in result.findings]
            ),
            suggested_actions_json=_json_dump(
                [item.model_dump(mode="json") for item in result.suggested_actions]
            ),
            duration_ms=result.duration_ms,
            skipped_reason=result.skipped_reason,
            correlation_id=result.correlation_id,
        )
        with db_session(self._settings) as session:
            session.add(record)
        return check_id

    def recent_events(self, limit: int = 50) -> list[Event]:
        safe_limit = min(max(limit, 1), 500)
        statement = (
            select(EventRecord)
            .order_by(col(EventRecord.timestamp).desc())
            .limit(safe_limit)
        )
        with db_session(self._settings) as session:
            records = session.exec(statement).all()
        return [_event_from_record(record) for record in records]

    def events_for_incident(self, incident: IncidentSummary, limit: int = 200) -> list[Event]:
        safe_limit = min(max(limit, 1), 500)
        statement = (
            select(EventRecord)
            .where(EventRecord.source == incident.source)
            .where(col(EventRecord.severity).in_(["warning", "critical"]))
            .order_by(col(EventRecord.timestamp).asc())
            .limit(safe_limit)
        )
        if incident.correlation_id:
            statement = statement.where(EventRecord.correlation_id == incident.correlation_id)
        with db_session(self._settings) as session:
            records = session.exec(statement).all()
        return [_event_from_record(record) for record in records]

    def prune(self, older_than: datetime) -> int:
        statement = delete(EventRecord).where(
            col(EventRecord.timestamp) < older_than.isoformat()
        )
        with db_session(self._settings) as session:
            result = session.exec(statement)
            return int(result.rowcount or 0)

    def prune_check_results(self, older_than: datetime) -> int:
        statement = delete(CheckResultRecord).where(
            col(CheckResultRecord.timestamp) < older_than.isoformat()
        )
        with db_session(self._settings) as session:
            result = session.exec(statement)
            return int(result.rowcount or 0)


class AuditRepository:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self._settings = settings or get_settings()

    def create(self, receipt: AuditReceipt) -> None:
        record = AuditRecord(
            id=receipt.id,
            timestamp=receipt.timestamp,
            tool_name=receipt.tool_name,
            caller=receipt.caller,
            arguments_json=_json_dump(receipt.arguments),
            safety=receipt.safety,
            confirmation_status=receipt.confirmation_status,
            result=receipt.result,
            result_data_json=_json_dump(receipt.result_data)
            if receipt.result_data is not None
            else None,
        )
        with db_session(self._settings) as session:
            session.merge(record)

    def update_result(self, audit_id: str, *, result: str, result_data: Any = None) -> None:
        with db_session(self._settings) as session:
            record = session.get(AuditRecord, audit_id)
            if record is None:
                return
            record.result = result
            record.result_data_json = (
                _json_dump(result_data) if result_data is not None else None
            )
            session.add(record)

    def recent(self, limit: int = 50) -> list[AuditReceipt]:
        safe_limit = min(max(limit, 1), 500)
        statement = (
            select(AuditRecord)
            .order_by(col(AuditRecord.timestamp).desc())
            .limit(safe_limit)
        )
        with db_session(self._settings) as session:
            records = session.exec(statement).all()
        return [_audit_from_record(record) for record in records]

    def by_ids(self, audit_ids: list[str]) -> list[AuditReceipt]:
        if not audit_ids:
            return []
        statement = select(AuditRecord).where(col(AuditRecord.id).in_(audit_ids))
        with db_session(self._settings) as session:
            records = session.exec(statement).all()
        return [_audit_from_record(record) for record in records]

    def prune(self, older_than: datetime) -> int:
        statement = delete(AuditRecord).where(
            col(AuditRecord.timestamp) < older_than.isoformat()
        )
        with db_session(self._settings) as session:
            result = session.exec(statement)
            return int(result.rowcount or 0)


class IncidentRepository:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._events = EventRepository(self._settings)

    def list_generated(self, limit: int = 50) -> list[IncidentSummary]:
        events = [
            event
            for event in self._events.recent_events(limit=500)
            if event.severity.lower() in {"warning", "critical"}
        ]
        grouped: dict[tuple[str, str | None], list[Event]] = {}
        for event in events:
            key = (event.source, event.correlation_id or event.type)
            grouped.setdefault(key, []).append(event)

        incidents = [self._summary_from_events(group) for group in grouped.values()]
        incidents.sort(key=lambda item: item.updated_at, reverse=True)
        return incidents[: min(max(limit, 1), 200)]

    def detail(self, incident_id: str) -> IncidentDetail | None:
        for incident in self.list_generated(limit=200):
            if incident.id != incident_id:
                continue
            events = self._events.events_for_incident(incident)
            audit_ids = [
                str(event.data.get("audit_id"))
                for event in events
                if event.data.get("audit_id") is not None
            ]
            audits = {
                audit.id: audit for audit in AuditRepository(self._settings).by_ids(audit_ids)
            }
            timeline = [_timeline_entry(event) for event in events]
            for audit in audits.values():
                timeline.append(
                    IncidentTimelineEntry(
                        timestamp=audit.timestamp,
                        source=audit.tool_name,
                        severity="info" if audit.result == "succeeded" else "warning",
                        summary=f"Write audit {audit.result}: {audit.tool_name}",
                        audit_id=audit.id,
                        suggested_action=audit.confirmation_status,
                    )
                )
            timeline.sort(key=lambda item: item.timestamp)
            return IncidentDetail(incident=incident, timeline=timeline)
        return None

    def prune(self, older_than_resolved: datetime, older_than_critical: datetime) -> int:
        resolved = (
            delete(IncidentRecord)
            .where(col(IncidentRecord.pinned).is_(False))
            .where(col(IncidentRecord.status) == "resolved")
            .where(col(IncidentRecord.updated_at) < older_than_resolved.isoformat())
        )
        critical = (
            delete(IncidentRecord)
            .where(col(IncidentRecord.pinned).is_(False))
            .where(col(IncidentRecord.status) == "closed")
            .where(col(IncidentRecord.severity) == "critical")
            .where(col(IncidentRecord.updated_at) < older_than_critical.isoformat())
        )
        with db_session(self._settings) as session:
            resolved_result = session.exec(resolved)
            critical_result = session.exec(critical)
            return int(resolved_result.rowcount or 0) + int(critical_result.rowcount or 0)

    def _summary_from_events(self, events: list[Event]) -> IncidentSummary:
        ordered = sorted(events, key=lambda event: event.timestamp)
        first = ordered[0]
        last = ordered[-1]
        severity = (
            "critical" if any(event.severity == "critical" for event in ordered) else "warning"
        )
        incident_key = first.correlation_id or f"{first.source}:{first.type}"
        return IncidentSummary(
            id=f"generated:{first.source}:{incident_key}",
            created_at=first.timestamp,
            updated_at=last.timestamp,
            source=first.source,
            title=f"{first.source} {severity} incident",
            severity=severity,
            status="open",
            correlation_id=first.correlation_id,
            pinned=False,
            event_count=len(ordered),
        )


def prune_durable_history(settings: AppSettings | None = None) -> dict[str, int]:
    resolved_settings = settings or get_settings()
    now = datetime.now(UTC)
    events = EventRepository(resolved_settings)
    audits = AuditRepository(resolved_settings)
    incidents = IncidentRepository(resolved_settings)
    return {
        "events": events.prune(now - timedelta(days=resolved_settings.event_retention_days)),
        "diagnostics": events.prune_check_results(
            now - timedelta(days=resolved_settings.diagnostic_retention_days)
        ),
        "audits": audits.prune(now - timedelta(days=resolved_settings.audit_retention_days)),
        "incidents": incidents.prune(
            now - timedelta(days=resolved_settings.resolved_incident_retention_days),
            now - timedelta(days=resolved_settings.critical_incident_retention_days),
        ),
    }


def _event_from_record(record: EventRecord) -> Event:
    return Event(
        id=record.id,
        timestamp=record.timestamp,
        type=record.type,
        severity=record.severity,
        source=record.source,
        payload_summary=record.payload_summary,
        correlation_id=record.correlation_id,
        data=_json_load(record.data_json, {}),
        findings=_json_load(record.findings_json, []),
        budget=_json_load(record.budget_json, None),
    )


def _audit_from_record(record: AuditRecord) -> AuditReceipt:
    return AuditReceipt(
        id=record.id,
        timestamp=record.timestamp,
        tool_name=record.tool_name,
        caller=record.caller,
        arguments=_json_load(record.arguments_json, {}),
        safety=record.safety,
        confirmation_status=record.confirmation_status,
        result=record.result,
        result_data=_json_load(record.result_data_json, None),
    )


def _timeline_entry(event: Event) -> IncidentTimelineEntry:
    evidence_summary = None
    suggested_action = None
    if event.findings:
        first_finding = event.findings[0]
        if first_finding.evidence:
            evidence_summary = first_finding.evidence[0].summary
        if first_finding.suggested_actions:
            suggested_action = first_finding.suggested_actions[0].description
    return IncidentTimelineEntry(
        timestamp=event.timestamp,
        source=event.source,
        severity=event.severity,
        summary=event.payload_summary,
        event_id=event.id,
        evidence_summary=evidence_summary,
        suggested_action=suggested_action,
    )
