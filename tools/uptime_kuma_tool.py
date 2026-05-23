from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from agent.mock_mode import MockMode
from agent.settings import get_settings
from agent.tools.base import ToolResult
from agent.tools.registry import ToolRegistry
from schemas.python.uptime_kuma import UptimeKumaMonitorStatusArgs, UptimeKumaRecentFailuresArgs


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="uptime_kuma_monitor_status",
        description="List Uptime Kuma monitor status, uptime ratio, and recent heartbeat state.",
        args_model=UptimeKumaMonitorStatusArgs,
    )(monitor_status)
    registry.register(
        name="uptime_kuma_recent_failures",
        description="List recent Uptime Kuma monitor failures and incidents.",
        args_model=UptimeKumaRecentFailuresArgs,
    )(recent_failures)


def monitor_status(arguments: BaseModel) -> ToolResult:
    args = UptimeKumaMonitorStatusArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("uptime_kuma_monitor_status", args)
    if mock_result is not None:
        return mock_result
    result = _request_json("/api/monitors")
    if not result.success:
        return result
    monitors = [
        _monitor_row(row)
        for row in _records(result.data, "monitors")
        if args.include_paused or not _truthy(row.get("paused"))
    ]
    return ToolResult(
        success=True,
        data={
            "monitor_count": len(monitors),
            "down_count": sum(1 for row in monitors if row["status"] == "down"),
            "degraded_count": sum(1 for row in monitors if row["status"] == "degraded"),
            "monitors": monitors,
        },
    )


def recent_failures(arguments: BaseModel) -> ToolResult:
    args = UptimeKumaRecentFailuresArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("uptime_kuma_recent_failures", args)
    if mock_result is not None:
        return mock_result
    result = _request_json("/api/incidents", params={"limit": args.limit})
    if not result.success:
        return result
    failures = [_failure_row(row) for row in _records(result.data, "incidents")][: args.limit]
    return ToolResult(success=True, data={"failure_count": len(failures), "failures": failures})


def _request_json(path: str, *, params: dict[str, Any] | None = None) -> ToolResult:
    settings = get_settings()
    if not settings.uptime_kuma.configured:
        return ToolResult(success=False, error="Uptime Kuma integration is not configured.")
    token = (
        settings.uptime_kuma_api_token.get_secret_value()
        if settings.uptime_kuma_api_token
        else ""
    )
    try:
        with httpx.Client(
            base_url=str(settings.uptime_kuma_base_url),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=10,
        ) as client:
            response = client.get(path, params=params)
            response.raise_for_status()
            return ToolResult(success=True, data=response.json())
    except httpx.HTTPError as exc:
        return ToolResult(success=False, error=f"Uptime Kuma request failed: {exc}")


def _monitor_row(row: dict[str, Any]) -> dict[str, Any]:
    raw_status = row.get("status", row.get("lastHeartbeatStatus", row.get("active")))
    status = _status(raw_status)
    return {
        "id": row.get("id"),
        "name": row.get("name") or row.get("friendly_name") or row.get("url") or "unknown",
        "url": row.get("url") or row.get("hostname"),
        "type": row.get("type"),
        "status": status,
        "uptime_ratio": row.get("uptime") or row.get("uptimeRatio") or row.get("uptime_24h"),
        "last_check": row.get("lastCheck") or row.get("lastHeartbeatTime") or row.get("time"),
        "message": row.get("msg") or row.get("message"),
        "paused": _truthy(row.get("paused")),
    }


def _failure_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "monitor_id": row.get("monitor_id") or row.get("monitorID") or row.get("id"),
        "monitor_name": row.get("monitor_name") or row.get("name") or row.get("title"),
        "status": _status(row.get("status")),
        "time": row.get("time") or row.get("created_at") or row.get("date"),
        "message": row.get("msg") or row.get("message") or row.get("content"),
    }


def _records(data: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        value = data.get(key) or data.get("data") or data.get("results")
    else:
        value = data
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _status(value: Any) -> str:
    normalized = str(value).lower()
    if normalized in {"0", "down", "fail", "failed", "false"}:
        return "down"
    if normalized in {"2", "pending", "degraded", "maintenance"}:
        return "degraded"
    if normalized in {"1", "up", "ok", "true", "running"}:
        return "up"
    return normalized or "unknown"


def _truthy(value: Any) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}
