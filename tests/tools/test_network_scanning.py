from __future__ import annotations

from typing import Any

import pytest

from agent.settings import AppSettings
from schemas.python.network import NetworkScanArgs, UnknownDeviceArgs
from tools import network_tool


def _settings(**overrides: Any) -> AppSettings:
    defaults: dict[str, Any] = {
        "network_allowed_subnets": ["192.168.1.0/24"],
        "network_known_macs": ["aa:bb:cc:dd:ee:ff"],
    }
    defaults.update(overrides)
    return AppSettings(**defaults)


def test_refuse_unsafe_subnet_rejects_public_ips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_tool, "get_settings", _settings)

    result = network_tool.network_scan(NetworkScanArgs(subnet="8.8.8.8/32"))

    assert result.success is False
    assert result.error is not None
    assert "RFC1918" in result.error


def test_refuse_unsafe_subnet_rejects_unallowed_private_ips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(network_tool, "get_settings", _settings)

    result = network_tool.network_scan(NetworkScanArgs(subnet="10.0.0.0/24"))

    assert result.success is False
    assert result.error is not None
    assert "network_allowed_subnets" in result.error


def test_network_scan_succeeds_for_allowed_subnet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_tool, "get_settings", _settings)

    xml_output = """<?xml version="1.0" ?>
    <nmaprun>
      <host>
        <status state="up" />
        <address addr="192.168.1.10" addrtype="ipv4" />
        <address addr="00:11:22:33:44:55" addrtype="mac" vendor="Acme Corp" />
        <hostnames><hostname name="test-host" /></hostnames>
        <ports></ports>
      </host>
    </nmaprun>
    """
    monkeypatch.setattr(network_tool, "run_nmap", lambda subnet, detect_services: xml_output)

    result = network_tool.network_scan(NetworkScanArgs(subnet="192.168.1.0/24"))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["subnet"] == "192.168.1.0/24"
    assert len(result.data["hosts"]) == 1
    host = result.data["hosts"][0]
    assert host["ip"] == "192.168.1.10"
    assert host["mac"] == "00:11:22:33:44:55"


def test_unknown_devices_filters_known_macs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_tool, "get_settings", _settings)

    xml_output = """<?xml version="1.0" ?>
    <nmaprun>
      <host>
        <address addr="192.168.1.10" addrtype="ipv4" />
        <address addr="AA:BB:CC:DD:EE:FF" addrtype="mac" /> <!-- Known, mixed case -->
      </host>
      <host>
        <address addr="192.168.1.11" addrtype="ipv4" />
        <address addr="11:22:33:44:55:66" addrtype="mac" /> <!-- Unknown -->
      </host>
    </nmaprun>
    """
    monkeypatch.setattr(network_tool, "run_nmap", lambda subnet, detect_services: xml_output)

    result = network_tool.network_unknown_devices(UnknownDeviceArgs(subnet="192.168.1.0/24"))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["unknown_count"] == 1
    assert len(result.data["unknown_devices"]) == 1
    assert result.data["unknown_devices"][0]["ip"] == "192.168.1.11"
