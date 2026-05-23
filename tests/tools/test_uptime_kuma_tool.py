from __future__ import annotations

import pytest

from agent.settings import AppSettings
from agent.tools.base import ToolResult
from schemas.python.uptime_kuma import UptimeKumaMonitorStatusArgs, UptimeKumaRecentFailuresArgs
from tools import uptime_kuma_tool


def test_monitor_status_summarizes_down_and_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        uptime_kuma_tool,
        "_request_json",
        lambda path, params=None: ToolResult(
            success=True,
            data={
                "monitors": [
                    {"id": 1, "name": "Plex", "status": 0, "url": "https://plex.example"},
                    {"id": 2, "name": "DNS", "status": 2},
                    {"id": 3, "name": "NAS", "status": 1},
                ]
            },
        ),
    )

    result = uptime_kuma_tool.monitor_status(UptimeKumaMonitorStatusArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["monitor_count"] == 3
    assert result.data["down_count"] == 1
    assert result.data["degraded_count"] == 1


def test_recent_failures_maps_incidents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        uptime_kuma_tool,
        "_request_json",
        lambda path, params=None: ToolResult(
            success=True,
            data={"incidents": [{"monitor_name": "Plex", "status": "down", "msg": "HTTP 502"}]},
        ),
    )

    result = uptime_kuma_tool.recent_failures(UptimeKumaRecentFailuresArgs(limit=5))

    assert result.success is True
    assert result.data == {
        "failure_count": 1,
        "failures": [
            {
                "monitor_id": None,
                "monitor_name": "Plex",
                "status": "down",
                "time": None,
                "message": "HTTP 502",
            }
        ],
    }


def test_uptime_kuma_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uptime_kuma_tool, "get_settings", lambda: AppSettings())

    result = uptime_kuma_tool._request_json("/api/monitors")

    assert result.success is False
    assert "not configured" in str(result.error)
