from __future__ import annotations

import shutil
import time
from typing import Any

from pydantic import BaseModel

from agent.mock_mode import MockMode
from agent.tools.base import ToolResult
from agent.tools.registry import ToolRegistry
from schemas.python.backups import BackupStorageHealthArgs
from schemas.python.proxmox import ProxmoxBackupJobsArgs, ProxmoxStorageArgs
from tools.proxmox_tool import backup_jobs, storage_usage


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="backup_storage_health",
        description=(
            "Summarize Proxmox backup job freshness, datastore free space, and local "
            "filesystem usage."
        ),
        args_model=BackupStorageHealthArgs,
    )(backup_storage_health)


def backup_storage_health(arguments: BaseModel) -> ToolResult:
    args = BackupStorageHealthArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("backup_storage_health", args, required=False)
    if mock_result is not None:
        return mock_result
    storage_result = storage_usage(ProxmoxStorageArgs())
    jobs_result = backup_jobs(ProxmoxBackupJobsArgs())
    if not storage_result.success:
        return storage_result
    if not jobs_result.success:
        return jobs_result

    storage_rows = _list_of_dicts(storage_result.data)
    job_rows = _list_of_dicts(jobs_result.data)
    local_rows = [_local_filesystem_row(path) for path in args.local_paths]
    findings = _storage_findings(storage_rows, args) + _job_findings(job_rows, args)
    findings.extend(_local_findings(local_rows, args.max_used_percent))
    return ToolResult(
        success=True,
        data={
            "status": "warning" if findings else "healthy",
            "findings": findings,
            "storage": storage_rows,
            "backup_jobs": job_rows,
            "local_filesystems": local_rows,
        },
    )


def _storage_findings(
    rows: list[dict[str, Any]], args: BackupStorageHealthArgs
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in rows:
        storage_id = str(row.get("storage", ""))
        threshold = args.datastore_thresholds.get(storage_id, args.max_used_percent)
        used_percent = _float(row.get("used_percent"))
        if used_percent >= threshold:
            findings.append(
                {
                    "severity": "warning",
                    "type": "storage_threshold",
                    "storage": storage_id,
                    "used_percent": used_percent,
                    "threshold_percent": threshold,
                    "next_action": "Free space or move backups before the datastore fills.",
                }
            )
    return findings


def _job_findings(
    rows: list[dict[str, Any]], args: BackupStorageHealthArgs
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    now = time.time()
    stale_after_seconds = args.stale_after_hours * 3600
    for row in rows:
        state = str(row.get("last_run_state") or "").lower()
        job_id = row.get("id")
        if state not in {"", "ok", "success", "completed"}:
            findings.append(
                {
                    "severity": "critical",
                    "type": "backup_job_failed",
                    "job_id": job_id,
                    "last_run_state": row.get("last_run_state"),
                    "next_action": "Inspect the Proxmox vzdump task log for the failed backup job.",
                }
            )
        endtime = _float(row.get("last_run_endtime"))
        if endtime <= 0 or now - endtime > stale_after_seconds:
            findings.append(
                {
                    "severity": "warning",
                    "type": "backup_job_stale",
                    "job_id": job_id,
                    "last_run_endtime": row.get("last_run_endtime"),
                    "stale_after_hours": args.stale_after_hours,
                    "next_action": (
                        "Confirm the backup schedule is enabled and the target storage "
                        "is reachable."
                    ),
                }
            )
    return findings


def _local_findings(rows: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    return [
        {
            "severity": "warning",
            "type": "local_filesystem_threshold",
            "path": row["path"],
            "used_percent": row["used_percent"],
            "threshold_percent": threshold,
            "next_action": "Free local disk space or move logs/artifacts off this filesystem.",
        }
        for row in rows
        if row.get("available", False) and _float(row.get("used_percent")) >= threshold
    ]


def _local_filesystem_row(path: str) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        return {"path": path, "available": False, "error": str(exc)}
    used = usage.total - usage.free
    used_percent = round((used / usage.total) * 100, 2) if usage.total else 0.0
    return {
        "path": path,
        "available": True,
        "used_percent": used_percent,
        "used_gb": round(used / 1_073_741_824, 2),
        "total_gb": round(usage.total / 1_073_741_824, 2),
    }


def _list_of_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
