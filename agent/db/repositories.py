from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from agent.db.session import db_connection
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
        with db_connection(self._settings) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO events (
                    id, timestamp, type, severity, source, payload_summary,
                    correlation_id, data_json, findings_json, budget_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.timestamp,
                    event.type,
                    event.severity,
                    event.source,
                    event.payload_summary,
                    event.correlation_id,
                    _json_dump(event.data),
                    _json_dump([finding.model_dump(mode="json") for finding in event.findings]),
                    event.budget.model_dump_json() if event.budget else None,
                ),
            )

    def store_check_result(self, result: ScheduledCheckResult) -> str:
        check_id = generate_id()
        with db_connection(self._settings) as connection:
            connection.execute(
                """
                INSERT INTO check_results (
                    id, timestamp, check_name, source, status, severity, summary,
                    evidence_json, findings_json, suggested_actions_json, duration_ms,
                    skipped_reason, correlation_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    check_id,
                    get_utc_now(),
                    result.check,
                    result.source,
                    result.status.value
                    if isinstance(result.status, CheckStatus)
                    else str(result.status),
                    result.severity,
                    result.summary,
                    _json_dump([item.model_dump(mode="json") for item in result.evidence]),
                    _json_dump([item.model_dump(mode="json") for item in result.findings]),
                    _json_dump(
                        [item.model_dump(mode="json") for item in result.suggested_actions]
                    ),
                    result.duration_ms,
                    result.skipped_reason,
                    result.correlation_id,
                ),
            )
        return check_id

    def recent_events(self, limit: int = 50) -> list[Event]:
        safe_limit = min(max(limit, 1), 500)
        with db_connection(self._settings) as connection:
            rows = connection.execute(
                """
                SELECT * FROM events
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def events_for_incident(self, incident: IncidentSummary, limit: int = 200) -> list[Event]:
        safe_limit = min(max(limit, 1), 500)
        query = """
            SELECT * FROM events
            WHERE source = ?
              AND severity IN ('warning', 'critical')
        """
        params: list[Any] = [incident.source]
        if incident.correlation_id:
            query += " AND correlation_id = ?"
            params.append(incident.correlation_id)
        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(safe_limit)
        with db_connection(self._settings) as connection:
            rows = connection.execute(query, params).fetchall()
        return [_event_from_row(row) for row in rows]

    def prune(self, older_than: datetime) -> int:
        cutoff = older_than.isoformat()
        with db_connection(self._settings) as connection:
            cursor = connection.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
            return int(cursor.rowcount)

    def prune_check_results(self, older_than: datetime) -> int:
        cutoff = older_than.isoformat()
        with db_connection(self._settings) as connection:
            cursor = connection.execute(
                "DELETE FROM check_results WHERE timestamp < ?",
                (cutoff,),
            )
            return int(cursor.rowcount)


class AuditRepository:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self._settings = settings or get_settings()

    def create(self, receipt: AuditReceipt) -> None:
        with db_connection(self._settings) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO audit_records (
                    id, timestamp, tool_name, caller, arguments_json, safety,
                    confirmation_status, result, result_data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.id,
                    receipt.timestamp,
                    receipt.tool_name,
                    receipt.caller,
                    _json_dump(receipt.arguments),
                    receipt.safety,
                    receipt.confirmation_status,
                    receipt.result,
                    _json_dump(receipt.result_data) if receipt.result_data is not None else None,
                ),
            )

    def update_result(self, audit_id: str, *, result: str, result_data: Any = None) -> None:
        with db_connection(self._settings) as connection:
            connection.execute(
                """
                UPDATE audit_records
                SET result = ?, result_data_json = ?
                WHERE id = ?
                """,
                (
                    result,
                    _json_dump(result_data) if result_data is not None else None,
                    audit_id,
                ),
            )

    def recent(self, limit: int = 50) -> list[AuditReceipt]:
        safe_limit = min(max(limit, 1), 500)
        with db_connection(self._settings) as connection:
            rows = connection.execute(
                """
                SELECT * FROM audit_records
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [_audit_from_row(row) for row in rows]

    def by_ids(self, audit_ids: list[str]) -> list[AuditReceipt]:
        if not audit_ids:
            return []
        placeholders = ",".join("?" for _ in audit_ids)
        with db_connection(self._settings) as connection:
            rows = connection.execute(
                f"SELECT * FROM audit_records WHERE id IN ({placeholders})",
                audit_ids,
            ).fetchall()
        return [_audit_from_row(row) for row in rows]

    def prune(self, older_than: datetime) -> int:
        cutoff = older_than.isoformat()
        with db_connection(self._settings) as connection:
            cursor = connection.execute(
                "DELETE FROM audit_records WHERE timestamp < ?",
                (cutoff,),
            )
            return int(cursor.rowcount)


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
                audit.id: audit
                for audit in AuditRepository(self._settings).by_ids(audit_ids)
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
        with db_connection(self._settings) as connection:
            resolved_cursor = connection.execute(
                """
                DELETE FROM incidents
                WHERE pinned = 0
                  AND status = 'resolved'
                  AND updated_at < ?
                """,
                (older_than_resolved.isoformat(),),
            )
            critical_cursor = connection.execute(
                """
                DELETE FROM incidents
                WHERE pinned = 0
                  AND status = 'closed'
                  AND severity = 'critical'
                  AND updated_at < ?
                """,
                (older_than_critical.isoformat(),),
            )
            return int(resolved_cursor.rowcount) + int(critical_cursor.rowcount)

    def _summary_from_events(self, events: list[Event]) -> IncidentSummary:
        ordered = sorted(events, key=lambda event: event.timestamp)
        first = ordered[0]
        last = ordered[-1]
        severity = (
            "critical"
            if any(event.severity == "critical" for event in ordered)
            else "warning"
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


def _event_from_row(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        timestamp=row["timestamp"],
        type=row["type"],
        severity=row["severity"],
        source=row["source"],
        payload_summary=row["payload_summary"],
        correlation_id=row["correlation_id"],
        data=_json_load(row["data_json"], {}),
        findings=_json_load(row["findings_json"], []),
        budget=_json_load(row["budget_json"], None),
    )


def _audit_from_row(row: sqlite3.Row) -> AuditReceipt:
    return AuditReceipt(
        id=row["id"],
        timestamp=row["timestamp"],
        tool_name=row["tool_name"],
        caller=row["caller"],
        arguments=_json_load(row["arguments_json"], {}),
        safety=row["safety"],
        confirmation_status=row["confirmation_status"],
        result=row["result"],
        result_data=_json_load(row["result_data_json"], None),
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
