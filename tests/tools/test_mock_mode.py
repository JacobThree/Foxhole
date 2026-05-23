from __future__ import annotations

import asyncio

import pytest

from agent import events
from schemas.python.arr import ArrQueueArgs, ArrService
from schemas.python.caddy import CaddyListRoutesArgs
from schemas.python.docker import DockerListContainersArgs
from schemas.python.network import PiholeSummaryArgs, UnknownDeviceArgs
from schemas.python.plex import PlexSessionsArgs
from schemas.python.proxmox import ProxmoxStorageArgs
from schemas.python.uptime_kuma import UptimeKumaMonitorStatusArgs
from tools import (
    arr_tool,
    caddy_tool,
    docker_tool,
    network_tool,
    plex_tool,
    proxmox_tool,
    uptime_kuma_tool,
)


def test_docker_mock_mode_avoids_docker_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOXHOLE_MOCK_MODE", "1")
    monkeypatch.setattr(
        docker_tool,
        "_docker_client",
        lambda: pytest.fail("Docker client should not be created in mock mode"),
    )

    result = docker_tool.list_containers(DockerListContainersArgs())

    assert result.success is True
    assert isinstance(result.data, list)
    assert result.data[0]["name"] == "plex-media-server"


def test_proxmox_mock_mode_avoids_api_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOXHOLE_MOCK_MODE", "1")
    monkeypatch.setattr(
        proxmox_tool,
        "_proxmox_client",
        lambda: pytest.fail("Proxmox client should not be created in mock mode"),
    )

    result = proxmox_tool.storage_usage(ProxmoxStorageArgs())

    assert result.success is True
    assert isinstance(result.data, list)
    assert result.data[0]["storage"] == "backup-nas"


def test_plex_mock_mode_avoids_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOXHOLE_MOCK_MODE", "1")
    monkeypatch.setattr(
        plex_tool,
        "_client",
        lambda settings: pytest.fail("Plex HTTP client should not be created in mock mode"),
    )

    result = plex_tool.active_sessions(PlexSessionsArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["session_count"] == 4


def test_arr_mock_mode_avoids_http_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOXHOLE_MOCK_MODE", "1")
    monkeypatch.setattr(
        arr_tool,
        "_request_json",
        lambda *args, **kwargs: pytest.fail("*Arr HTTP request should not run in mock mode"),
    )

    result = arr_tool.queue(ArrQueueArgs(service=ArrService.SONARR))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["records"][0]["id"] == 7


def test_network_mock_mode_avoids_pihole_and_nmap_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOXHOLE_MOCK_MODE", "1")
    monkeypatch.setattr(
        network_tool,
        "_pihole_client",
        lambda settings: pytest.fail("Pi-hole HTTP client should not run in mock mode"),
    )
    monkeypatch.setattr(
        network_tool,
        "run_nmap",
        lambda *args, **kwargs: pytest.fail("nmap should not run in mock mode"),
    )

    summary = network_tool.pihole_summary(PiholeSummaryArgs())
    unknown = network_tool.network_unknown_devices(UnknownDeviceArgs(subnet="192.168.1.0/24"))

    assert summary.success is True
    assert isinstance(summary.data, dict)
    assert summary.data["domains_being_blocked"] == 0
    assert unknown.success is True
    assert isinstance(unknown.data, dict)
    assert unknown.data["unknown_count"] == 1


def test_uptime_kuma_mock_mode_avoids_http_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOXHOLE_MOCK_MODE", "1")
    monkeypatch.setattr(
        uptime_kuma_tool,
        "_request_json",
        lambda *args, **kwargs: pytest.fail("Uptime Kuma HTTP request should not run in mock mode"),
    )

    result = uptime_kuma_tool.monitor_status(UptimeKumaMonitorStatusArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["down_count"] == 1


def test_caddy_mock_mode_avoids_file_or_admin_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOXHOLE_MOCK_MODE", "1")
    monkeypatch.setattr(
        caddy_tool,
        "_admin_config_routes",
        lambda *args, **kwargs: pytest.fail("Caddy admin API should not run in mock mode"),
    )

    result = caddy_tool.list_routes(CaddyListRoutesArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["route_count"] == 2


def test_events_can_be_served_from_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOXHOLE_MOCK_MODE", "1")

    recent = asyncio.run(events.get_recent_events(limit=1))

    assert len(recent) == 1
    assert recent[0].source == "docker"
