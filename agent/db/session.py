from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from agent.settings import AppSettings, get_settings


def database_path(settings: AppSettings | None = None) -> str:
    return (settings or get_settings()).database_path


@contextmanager
def db_connection(settings: AppSettings | None = None) -> Iterator[sqlite3.Connection]:
    path = database_path(settings)
    if path != ":memory:":
        resolved_path = str(Path(path).expanduser())
        Path(resolved_path).parent.mkdir(parents=True, exist_ok=True)
    else:
        resolved_path = path
    connection = sqlite3.connect(resolved_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    initialize_database(connection)
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            type TEXT NOT NULL,
            severity TEXT NOT NULL,
            source TEXT NOT NULL,
            payload_summary TEXT NOT NULL,
            correlation_id TEXT,
            data_json TEXT NOT NULL,
            findings_json TEXT NOT NULL,
            budget_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
        CREATE INDEX IF NOT EXISTS idx_events_correlation ON events(correlation_id);

        CREATE TABLE IF NOT EXISTS check_results (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            check_name TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            severity TEXT NOT NULL,
            summary TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            findings_json TEXT NOT NULL,
            suggested_actions_json TEXT NOT NULL,
            duration_ms REAL NOT NULL,
            skipped_reason TEXT,
            correlation_id TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_check_results_timestamp
            ON check_results(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_check_results_correlation
            ON check_results(correlation_id);

        CREATE TABLE IF NOT EXISTS audit_records (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            caller TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            safety TEXT NOT NULL,
            confirmation_status TEXT NOT NULL,
            result TEXT NOT NULL,
            result_data_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_audit_records_timestamp
            ON audit_records(timestamp DESC);

        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            correlation_id TEXT,
            pinned INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_incidents_updated_at ON incidents(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_incidents_source ON incidents(source);
        """
    )
