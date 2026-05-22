from __future__ import annotations

from typing import Any

import httpx
from pydantic import SecretStr

from agent.settings import AppSettings
from agent.tools.registry import ToolRegistry
from schemas.python.arr import (
    ArrHealthArgs,
    ArrImportDiagnosisArgs,
    ArrQueueArgs,
    ArrService,
)
from tools import arr_tool


def _settings() -> AppSettings:
    return AppSettings(
        sonarr_base_url="http://sonarr.local",
        sonarr_api_key=SecretStr("sonarr-key"),
        radarr_base_url="http://radarr.local",
        radarr_api_key=SecretStr("radarr-key"),
    )


def _patch(monkeypatch, handler) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return handler(request)

    transport = httpx.MockTransport(wrapped)
    monkeypatch.setattr(arr_tool, "get_settings", _settings)
    def make_client(integration):
        api_key = integration.api_key.get_secret_value() if integration.api_key else ""
        return httpx.Client(
            base_url=str(integration.base_url),
            headers={"X-Api-Key": api_key},
            transport=transport,
        )

    monkeypatch.setattr(arr_tool, "_client", make_client)
    return captured


def test_arr_diagnostic_tools_register_expected_names() -> None:
    registry = ToolRegistry()
    arr_tool.register_tools(registry)

    assert {tool.name for tool in registry.list()} == {
        "arr_queue",
        "arr_health",
        "arr_root_folders",
        "arr_download_clients",
        "arr_quality_profiles",
        "arr_import_diagnosis",
    }


def test_queue_uses_x_api_key_and_records(monkeypatch) -> None:
    captured = _patch(
        monkeypatch,
        lambda req: httpx.Response(
            200,
            json={
                "records": [
                    {"id": 1, "title": "Episode 1", "status": "warning"},
                ]
            },
        ),
    )

    result = arr_tool.queue(ArrQueueArgs(service=ArrService.SONARR))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["records"][0]["title"] == "Episode 1"
    assert captured["request"].headers["X-Api-Key"] == "sonarr-key"
    assert captured["request"].url.path == "/api/v3/queue"


def test_health_returns_records_for_radarr(monkeypatch) -> None:
    captured = _patch(
        monkeypatch,
        lambda req: httpx.Response(200, json=[{"source": "IndexerStatus", "type": "warning"}]),
    )

    result = arr_tool.health(ArrHealthArgs(service=ArrService.RADARR))

    assert result.success is True
    assert isinstance(result.data, list)
    assert result.data[0]["source"] == "IndexerStatus"
    assert captured["request"].headers["X-Api-Key"] == "radarr-key"


def test_import_diagnosis_flags_path_outside_root(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/queue":
            return httpx.Response(
                200,
                json={
                    "records": [
                        {
                            "id": 7,
                            "title": "Show S01E01",
                            "outputPath": "/downloads/complete/Show S01E01",
                            "status": "warning",
                            "statusMessages": [
                                {"title": "Show S01E01", "messages": ["No files found"]}
                            ],
                        },
                        {
                            "id": 8,
                            "title": "Other S01E02",
                            "outputPath": "/tv/Other/Season 01",
                            "status": "completed",
                        },
                    ]
                },
            )
        if request.url.path == "/api/v3/rootfolder":
            return httpx.Response(200, json=[{"path": "/tv"}])
        return httpx.Response(404)

    _patch(monkeypatch, handler)

    result = arr_tool.import_diagnosis(ArrImportDiagnosisArgs(service=ArrService.SONARR))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["root_folders"] == ["/tv"]
    assert result.data["mismatch_count"] == 1
    mismatch = result.data["mismatches"][0]
    assert mismatch["queue_id"] == 7
    assert mismatch["output_path"] == "/downloads/complete/Show S01E01"
    assert "No files found" in mismatch["tracked_messages"]


def test_queue_returns_not_configured_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(arr_tool, "get_settings", lambda: AppSettings())

    result = arr_tool.queue(ArrQueueArgs(service=ArrService.SONARR))

    assert result.success is False
    assert "not configured" in (result.error or "")


def test_sonarr_and_radarr_use_independent_keys(monkeypatch) -> None:
    seen_keys: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_keys.append(request.headers["X-Api-Key"])
        return httpx.Response(200, json=[])

    _patch(monkeypatch, handler)

    arr_tool.health(ArrHealthArgs(service=ArrService.SONARR))
    arr_tool.health(ArrHealthArgs(service=ArrService.RADARR))

    assert seen_keys == ["sonarr-key", "radarr-key"]
