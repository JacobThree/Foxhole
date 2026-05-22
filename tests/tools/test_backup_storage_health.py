from __future__ import annotations

import time

from agent.tools.base import ToolResult
from schemas.python.backups import BackupStorageHealthArgs
from tools import backup_tool


def test_backup_storage_health_reports_thresholds_and_failed_jobs(monkeypatch) -> None:
    monkeypatch.setattr(
        backup_tool,
        "storage_usage",
        lambda arguments: ToolResult(
            success=True,
            data=[
                {
                    "node": "pve",
                    "storage": "backup",
                    "used_percent": 91.0,
                    "used_gb": 910,
                    "total_gb": 1000,
                }
            ],
        ),
    )
    monkeypatch.setattr(
        backup_tool,
        "backup_jobs",
        lambda arguments: ToolResult(
            success=True,
            data=[
                {
                    "id": "backup-all",
                    "last_run_state": "error",
                    "last_run_endtime": time.time() - (72 * 3600),
                }
            ],
        ),
    )

    result = backup_tool.backup_storage_health(
        BackupStorageHealthArgs(max_used_percent=85, stale_after_hours=24)
    )

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["status"] == "warning"
    finding_types = {finding["type"] for finding in result.data["findings"]}
    assert finding_types == {"storage_threshold", "backup_job_failed", "backup_job_stale"}


def test_backup_storage_health_healthy_when_no_findings(monkeypatch) -> None:
    monkeypatch.setattr(
        backup_tool,
        "storage_usage",
        lambda arguments: ToolResult(
            success=True,
            data=[{"storage": "backup", "used_percent": 50.0}],
        ),
    )
    monkeypatch.setattr(
        backup_tool,
        "backup_jobs",
        lambda arguments: ToolResult(
            success=True,
            data=[{"id": "backup-all", "last_run_state": "ok", "last_run_endtime": time.time()}],
        ),
    )

    result = backup_tool.backup_storage_health(BackupStorageHealthArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["status"] == "healthy"
    assert result.data["findings"] == []
