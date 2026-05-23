from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from agent.settings import AppSettings, get_settings
from agent.tools.base import ToolResult
from workers import tasks
from workers.tasks import (
    check_arr_imports,
    check_container_health,
    check_plex_db_health,
    check_storage_thresholds,
    scan_rogue_macs,
)


@pytest.fixture(autouse=True)
def no_event_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr(tasks, "_emit_check_result", lambda result: None)
    yield
    get_settings.cache_clear()


def test_tasks_return_shared_check_envelope() -> None:
    results = [
        check_container_health.run(),
        check_storage_thresholds.run(),
        check_arr_imports.run(),
        check_plex_db_health.run(),
        scan_rogue_macs.run(),
    ]

    assert {result["status"] for result in results} == {"skipped"}
    for result in results:
        assert result["check"]
        assert result["source"]
        assert result["severity"] == "info"
        assert result["skipped_reason"]
        assert isinstance(result["evidence"], list)
        assert result["duration_ms"] >= 0
        assert result["correlation_id"]


def test_container_health_flags_restart_and_security_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tasks,
        "get_settings",
        lambda: AppSettings(docker_enabled=True, docker_socket_proxy_url="tcp://proxy:2375"),
    )
    monkeypatch.setattr(
        tasks.docker_tool,
        "list_containers",
        lambda args: ToolResult(
            success=True,
            data=[
                {
                    "id": "abc",
                    "name": "plex",
                    "status": "running",
                    "health": "unhealthy",
                    "restart_count": 4,
                }
            ],
        ),
    )
    monkeypatch.setattr(
        tasks.docker_tool,
        "detect_restart_loops",
        lambda args: ToolResult(
            success=True,
            data={
                "restart_loop_candidates": [
                    {"id": "abc", "name": "plex", "status": "running", "restart_count": 4}
                ]
            },
        ),
    )
    monkeypatch.setattr(
        tasks.security_tool,
        "security_posture",
        lambda args: ToolResult(
            success=True,
            data={
                "findings": [
                    {
                        "severity": "high",
                        "type": "privileged_container",
                        "evidence": "Container 'plex' is privileged.",
                        "remediation": "Remove --privileged.",
                    },
                    {
                        "severity": "low",
                        "type": "missing_restart_policy",
                        "evidence": "Container 'plex' has no restart policy.",
                        "remediation": "Set unless-stopped.",
                    },
                ]
            },
        ),
    )

    result = check_container_health.run()

    assert result["status"] == "critical"
    titles = {finding["title"] for finding in result["findings"]}
    assert "Unhealthy Docker Container" not in titles
    assert "Unhealthy Docker container" in titles
    assert "Docker restart loop candidate" in titles
    assert "Privileged Container" in titles


def test_storage_thresholds_maps_backup_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tasks,
        "get_settings",
        lambda: AppSettings(
            proxmox_enabled=True,
            proxmox_host="https://pve.local:8006",
            proxmox_token_id=SecretStr("root@pam!foxhole"),
            proxmox_token_secret=SecretStr("secret"),
        ),
    )
    monkeypatch.setattr(
        tasks.backup_tool,
        "backup_storage_health",
        lambda args: ToolResult(
            success=True,
            data={
                "status": "warning",
                "findings": [
                    {
                        "severity": "critical",
                        "type": "backup_job_failed",
                        "job_id": "backup-all",
                        "last_run_state": "error",
                        "next_action": "Inspect backup logs.",
                    }
                ],
                "storage": [],
                "backup_jobs": [{"id": "backup-all"}],
            },
        ),
    )

    result = check_storage_thresholds.run()

    assert result["status"] == "critical"
    assert result["findings"][0]["title"] == "Backup Job Failed"
    assert "backup-all" in result["findings"][0]["summary"]


def test_arr_imports_reports_stale_queue_and_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_added = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    monkeypatch.setattr(
        tasks,
        "get_settings",
        lambda: AppSettings(
            sonarr_enabled=True,
            sonarr_base_url="http://sonarr.local",
            sonarr_api_key=SecretStr("key"),
        ),
    )
    monkeypatch.setattr(
        tasks.arr_tool,
        "queue",
        lambda args: ToolResult(
            success=True,
            data={
                "records": [
                    {
                        "id": 7,
                        "title": "Show S01E01",
                        "status": "warning",
                        "added": old_added,
                        "statusMessages": [{"messages": ["No files found"]}],
                    }
                ]
            },
        ),
    )
    monkeypatch.setattr(tasks.arr_tool, "health", lambda args: ToolResult(success=True, data=[]))
    monkeypatch.setattr(
        tasks.arr_tool,
        "import_diagnosis",
        lambda args: ToolResult(
            success=True,
            data={
                "mismatches": [
                    {
                        "queue_id": 7,
                        "title": "Show S01E01",
                        "output_path": "/downloads/complete/show",
                        "expected_roots": ["/tv"],
                    }
                ]
            },
        ),
    )

    result = check_arr_imports.run()

    assert result["status"] == "warning"
    titles = {finding["title"] for finding in result["findings"]}
    assert "Sonarr queue warning" in titles
    assert "Sonarr stale import queue item" in titles
    assert "Sonarr root-folder mismatch" in titles
    assert any(action["requires_confirmation"] for action in result["suggested_actions"])


def test_plex_db_health_uses_log_path_and_buffering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tasks,
        "get_settings",
        lambda: AppSettings(
            plex_enabled=True,
            plex_base_url="http://plex.local:32400",
            plex_token=SecretStr("token"),
            plex_log_path="/logs/Plex Media Server.log",
        ),
    )
    monkeypatch.setattr(
        tasks.plex_tool,
        "buffering_diagnosis",
        lambda args: ToolResult(
            success=True,
            data={
                "risk": "high",
                "risk_factors": ["1 session using software transcoding"],
                "session_count": 3,
                "software_transcode_count": 1,
            },
        ),
    )
    monkeypatch.setattr(
        tasks.plex_tool,
        "analyze_logs",
        lambda args: ToolResult(
            success=True,
            data={
                "log_path": "/logs/Plex Media Server.log",
                "bytes_read": 1000,
                "finding_counts": {"sqlite_busy": 1},
                "findings": [
                    {
                        "category": "sqlite_busy",
                        "severity": "warning",
                        "line": "database is locked",
                    }
                ],
            },
        ),
    )

    result = check_plex_db_health.run()

    assert result["status"] == "critical"
    titles = {finding["title"] for finding in result["findings"]}
    assert "Plex buffering risk" in titles
    assert "Sqlite Busy" in titles


def test_network_scan_skips_when_no_allowed_subnets() -> None:
    result = scan_rogue_macs.run()

    assert result["status"] == "skipped"
    assert "No allowed subnets" in result["skipped_reason"]


def test_network_scan_reports_unknown_devices_and_dns_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tasks,
        "get_settings",
        lambda: AppSettings(
            network_allowed_subnets=["192.168.1.0/24"],
            network_known_macs=["aa:bb:cc:dd:ee:ff"],
            pihole_enabled=True,
            pihole_base_url="http://pihole.local",
            pihole_api_token=SecretStr("token"),
            unbound_enabled=True,
            unbound_host="unbound.local",
        ),
    )
    monkeypatch.setattr(
        tasks.network_tool,
        "network_unknown_devices",
        lambda args: ToolResult(
            success=True,
            data={
                "subnet": "192.168.1.0/24",
                "unknown_count": 1,
                "unknown_devices": [
                    {
                        "ip": "192.168.1.50",
                        "mac": "11:22:33:44:55:66",
                        "vendor": "Acme",
                    }
                ],
            },
        ),
    )
    monkeypatch.setattr(
        tasks.network_tool,
        "pihole_summary",
        lambda args: ToolResult(
            success=True,
            data={
                "dns_queries_today": 100,
                "ads_blocked_today": 20,
                "ads_percentage_today": 20.0,
                "domains_being_blocked": 100000,
            },
        ),
    )
    monkeypatch.setattr(
        tasks.network_tool,
        "unbound_stats",
        lambda args: ToolResult(
            success=True,
            data={"total.num.queries": 10, "total.num.cachehits": 7, "time.up": 1000},
        ),
    )

    result = scan_rogue_macs.run()

    assert result["status"] == "warning"
    assert result["findings"][0]["title"] == "Unknown MAC detected"
    evidence_sources = {item["source"] for item in result["evidence"]}
    assert {"network_unknown_devices", "pihole_summary", "unbound_stats"} <= evidence_sources
