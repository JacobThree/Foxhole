from __future__ import annotations

import httpx
from pydantic import SecretStr

from agent.settings import AppSettings
from agent.tools.registry import ToolRegistry
from schemas.python.observability import (
    FaultTimelineArgs,
    OverseerrFailedRequestsArgs,
    OverseerrRequestsArgs,
    TautulliHistoryArgs,
)
from tools import observability_tool


def _settings() -> AppSettings:
    return AppSettings(
        tautulli_enabled=True, tautulli_base_url="http://tautulli.local",
        tautulli_api_key=SecretStr("taut-key"),
        overseerr_enabled=True, overseerr_base_url="http://overseerr.local",
        overseerr_api_key=SecretStr("over-key"),
    )


def test_observability_tools_register_expected_names() -> None:
    registry = ToolRegistry()
    observability_tool.register_tools(registry)

    assert {tool.name for tool in registry.list()} == {
        "tautulli_recent_history",
        "tautulli_status",
        "overseerr_requests",
        "overseerr_failed_requests",
        "media_fault_timeline",
    }


def test_tautulli_uses_apikey_query_param(monkeypatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200, json={"response": {"result": "success", "data": {"data": []}}}
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(observability_tool, "get_settings", _settings)
    monkeypatch.setattr(
        observability_tool,
        "_tautulli_client",
        lambda settings: httpx.Client(
            base_url=str(settings.tautulli_base_url), transport=transport
        ),
    )

    result = observability_tool.tautulli_recent_history(TautulliHistoryArgs(length=10))

    assert result.success is True
    assert captured["request"].url.params["apikey"] == "taut-key"
    assert captured["request"].url.params["cmd"] == "get_history"


def test_overseerr_uses_x_api_key_header(monkeypatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(observability_tool, "get_settings", _settings)

    def make_client(integration):
        api_key = integration.api_key.get_secret_value() if integration.api_key else ""
        return httpx.Client(
            base_url=str(integration.base_url),
            headers={"X-Api-Key": api_key},
            transport=transport,
        )

    monkeypatch.setattr(observability_tool, "_overseerr_client", make_client)

    result = observability_tool.overseerr_requests(OverseerrRequestsArgs(take=5))

    assert result.success is True
    assert captured["request"].headers["X-Api-Key"] == "over-key"


def test_overseerr_failed_requests_cross_checks_status(monkeypatch) -> None:
    handler = lambda req: httpx.Response(  # noqa: E731
        200,
        json={
            "results": [
                {"id": 1, "status": 2, "media": {"status": 5, "title": "Foo"}, "type": "movie"},
                {"id": 2, "status": 1, "media": {"status": 5, "title": "Bar"}, "type": "tv"},
                {"id": 3, "status": 4, "media": {"status": 1, "title": "Baz"}, "type": "movie"},
            ]
        },
    )
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(observability_tool, "get_settings", _settings)
    monkeypatch.setattr(
        observability_tool,
        "_overseerr_client",
        lambda integration: httpx.Client(
            base_url=str(integration.base_url), transport=transport
        ),
    )

    result = observability_tool.overseerr_failed_requests(
        OverseerrFailedRequestsArgs(take=10)
    )

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["count"] == 3


def test_fault_timeline_merges_by_timestamp_and_source(monkeypatch) -> None:
    def tautulli_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": {
                    "result": "success",
                    "data": {
                        "data": [
                            {
                                "date": 1_700_000_500,
                                "full_title": "Plex Title",
                                "user": "alice",
                                "watched_status": 0.5,
                            }
                        ]
                    },
                }
            },
        )

    monkeypatch.setattr(observability_tool, "get_settings", _settings)
    monkeypatch.setattr(
        observability_tool,
        "_tautulli_client",
        lambda settings: httpx.Client(
            base_url=str(settings.tautulli_base_url),
            transport=httpx.MockTransport(tautulli_handler),
        ),
    )
    monkeypatch.setattr(
        observability_tool,
        "overseerr_failed_requests",
        lambda args: observability_tool.ToolResult(
            success=True,
            data={
                "count": 1,
                "requests": [
                    {
                        "id": 9,
                        "status": 4,
                        "media_status": 5,
                        "media_title": "Overseerr Title",
                        "updated_at": "1700000600",
                        "requested_by": "bob",
                    }
                ],
            },
        ),
    )

    result = observability_tool.fault_timeline(FaultTimelineArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    sources = {event["source"] for event in result.data["events"]}
    assert sources == {"tautulli", "overseerr"}
    assert result.data["event_count"] == 2


def test_fault_timeline_returns_empty_when_no_integrations(monkeypatch) -> None:
    monkeypatch.setattr(observability_tool, "get_settings", lambda: AppSettings())

    result = observability_tool.fault_timeline(FaultTimelineArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["events"] == []
    assert result.data["sources_queried"] == []
