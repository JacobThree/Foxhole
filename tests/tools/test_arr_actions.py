from __future__ import annotations

from typing import Any

import httpx
from pydantic import SecretStr

from agent.safety import AuditLog, WritePolicy
from agent.settings import AppSettings
from agent.tools.base import ToolSafety
from agent.tools.registry import ToolRegistry
from schemas.python.arr import (
    ArrQualityProfileUpdateArgs,
    ArrQueueItemActionArgs,
    ArrService,
)
from tools import arr_tool


def _settings() -> AppSettings:
    return AppSettings(
        sonarr_base_url="http://sonarr.local",
        sonarr_api_key=SecretStr("sonarr-key"),
    )


def _patch(monkeypatch, handler) -> dict[str, Any]:
    captured: dict[str, list[httpx.Request]] = {"requests": []}

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured["requests"].append(request)
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


def test_write_tools_register_with_confirmation_safety() -> None:
    registry = ToolRegistry()
    arr_tool.register_write_tools(registry)

    update = registry.get("arr_update_quality_profile")
    queue_action = registry.get("arr_queue_item_action")
    assert update.safety is ToolSafety.REQUIRES_CONFIRMATION
    assert queue_action.safety is ToolSafety.REQUIRES_CONFIRMATION


def test_unconfirmed_profile_update_is_blocked() -> None:
    registry = ToolRegistry()
    arr_tool.register_write_tools(registry)
    tool = registry.get("arr_update_quality_profile")
    args = ArrQualityProfileUpdateArgs(
        service=ArrService.SONARR, profile_id=4, name="HD-1080p", upgrade_allowed=False
    )
    policy = WritePolicy(
        AppSettings(write_stage=2, write_confirmation_secret=SecretStr("secret"))
    )

    decision = policy.evaluate(tool=tool, caller="test", arguments=args)

    assert decision.allowed is False
    assert decision.write_action.confirmation_required is True


def test_profile_update_returns_before_after_diff(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": 4,
                    "name": "Any",
                    "upgradeAllowed": True,
                    "cutoff": 1,
                    "items": [],
                },
            )
        if request.method == "PUT":
            payload = httpx._utils.to_str(request.content) if request.content else "{}"
            assert "HD-1080p" in payload
            return httpx.Response(
                200,
                json={"id": 4, "name": "HD-1080p", "upgradeAllowed": False, "items": []},
            )
        return httpx.Response(405)

    _patch(monkeypatch, handler)

    result = arr_tool.update_quality_profile(
        ArrQualityProfileUpdateArgs(
            service=ArrService.SONARR,
            profile_id=4,
            name="HD-1080p",
            upgrade_allowed=False,
        )
    )

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["before"] == {"name": "Any", "upgradeAllowed": True}
    assert result.data["after"] == {"name": "HD-1080p", "upgradeAllowed": False}


def test_queue_item_action_calls_delete_with_flags(monkeypatch) -> None:
    captured = _patch(
        monkeypatch, lambda req: httpx.Response(200, json={})
    )

    result = arr_tool.queue_item_action(
        ArrQueueItemActionArgs(
            service=ArrService.SONARR, queue_id=42, remove_from_client=True, blocklist=True
        )
    )

    assert result.success is True
    request = captured["requests"][0]
    assert request.method == "DELETE"
    assert request.url.path == "/api/v3/queue/42"
    assert request.url.params["removeFromClient"] == "true"
    assert request.url.params["blocklist"] == "true"


def test_audit_log_records_confirmed_write() -> None:
    audit_log = AuditLog()
    policy = WritePolicy(
        AppSettings(write_stage=2, write_confirmation_secret=SecretStr("secret")),
        audit_log,
    )
    registry = ToolRegistry()
    arr_tool.register_write_tools(registry)
    tool = registry.get("arr_update_quality_profile")
    args = ArrQualityProfileUpdateArgs(
        service=ArrService.SONARR, profile_id=4, name="HD-1080p", upgrade_allowed=False
    )
    token = policy.confirmation_token(tool.name, "test", args.model_dump(mode="json"))

    decision = policy.evaluate(
        tool=tool, caller="test", arguments=args, confirmation_token=token
    )

    assert decision.allowed is True
    assert audit_log.events[0].confirmation_status == "confirmed"
