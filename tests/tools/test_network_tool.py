from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from agent.settings import AppSettings
from agent.tools.registry import ToolRegistry
from schemas.python.network import (
    PiholeQueriesArgs,
    PiholeSummaryArgs,
    UnboundStatsArgs,
)
from tools import network_tool


def _settings(**overrides: Any) -> AppSettings:
    defaults: dict[str, Any] = {
        "pihole_base_url": "http://pihole.local",
        "pihole_api_token": SecretStr("pi-token"),
        "unbound_host": "unbound.local",
    }
    defaults.update(overrides)
    return AppSettings(**defaults)


def test_network_tools_register_expected_names() -> None:
    registry = ToolRegistry()
    network_tool.register_tools(registry)

    assert {tool.name for tool in registry.list()} == {
        "pihole_summary",
        "pihole_recent_blocked",
        "pihole_recent_queries",
        "unbound_stats",
        "network_scan",
        "network_unknown_devices",
    }


def test_pihole_summary_sends_auth_token(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"ads_blocked_today": 42, "domains_being_blocked": 100000})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(network_tool, "get_settings", _settings)
    monkeypatch.setattr(
        network_tool,
        "_pihole_client",
        lambda settings: httpx.Client(
            base_url=str(settings.pihole_base_url), transport=transport
        ),
    )

    result = network_tool.pihole_summary(PiholeSummaryArgs())

    assert result.success is True
    request = captured["request"]
    assert request.url.params["auth"] == "pi-token"
    assert "summary" in request.url.params


def test_pihole_recent_queries_passes_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"data": [["1700000000", "A", "example.com", "client"]]})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(network_tool, "get_settings", _settings)
    monkeypatch.setattr(
        network_tool,
        "_pihole_client",
        lambda settings: httpx.Client(
            base_url=str(settings.pihole_base_url), transport=transport
        ),
    )

    result = network_tool.pihole_recent_queries(PiholeQueriesArgs(limit=25))

    assert result.success is True
    assert captured["request"].url.params["getAllQueries"] == "25"


def test_pihole_missing_token_returns_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_tool, "get_settings", lambda: AppSettings())

    result = network_tool.pihole_summary(PiholeSummaryArgs())

    assert result.success is False
    assert result.error is not None
    assert "not configured" in result.error


def test_pihole_empty_list_indicates_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
    monkeypatch.setattr(network_tool, "get_settings", _settings)
    monkeypatch.setattr(
        network_tool,
        "_pihole_client",
        lambda settings: httpx.Client(
            base_url=str(settings.pihole_base_url), transport=transport
        ),
    )

    result = network_tool.pihole_summary(PiholeSummaryArgs())

    assert result.success is False
    assert result.error is not None
    assert "auth" in result.error.lower()


def test_parse_unbound_stats_parses_key_value_lines() -> None:
    output = (
        "total.num.queries=12345\n"
        "total.num.cachehits=8000\n"
        "total.requestlist.avg=0.42\n"
        "time.up=98765.123\n"
        "\n"
        "garbage line without equals\n"
    )

    metrics = network_tool.parse_unbound_stats(output)

    assert metrics["total.num.queries"] == 12345
    assert metrics["total.num.cachehits"] == 8000
    assert metrics["total.requestlist.avg"] == pytest.approx(0.42)
    assert "garbage line without equals" not in metrics


def test_unbound_stats_returns_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network_tool, "get_settings", _settings)
    monkeypatch.setattr(
        network_tool,
        "run_unbound_control",
        lambda settings: "total.num.queries=10\ntotal.num.cachehits=7\n",
    )

    result = network_tool.unbound_stats(UnboundStatsArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["total.num.queries"] == 10


def test_unbound_missing_binary_returns_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_missing(settings: AppSettings) -> str:
        raise FileNotFoundError("unbound-control")

    monkeypatch.setattr(network_tool, "get_settings", _settings)
    monkeypatch.setattr(network_tool, "run_unbound_control", raise_missing)

    result = network_tool.unbound_stats(UnboundStatsArgs())

    assert result.success is False
    assert result.error is not None
    assert "unbound-control" in result.error
