from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from agent.settings import AppSettings, IntegrationSettings, get_settings
from agent.tools.base import ToolResult
from agent.tools.registry import ToolRegistry
from schemas.python.observability import (
    FaultTimelineArgs,
    OverseerrFailedRequestsArgs,
    OverseerrRequestsArgs,
    TautulliHistoryArgs,
)

_OVERSEERR_FAILURE_STATUSES = {3, 4, 5}


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="tautulli_recent_history",
        description="Read recent Tautulli watch history with bounded length.",
        args_model=TautulliHistoryArgs,
    )(tautulli_recent_history)
    registry.register(
        name="tautulli_status",
        description="Read Tautulli version and server status.",
        args_model=TautulliHistoryArgs,
    )(tautulli_status)
    registry.register(
        name="overseerr_requests",
        description="List Overseerr requests with optional filter.",
        args_model=OverseerrRequestsArgs,
    )(overseerr_requests)
    registry.register(
        name="overseerr_failed_requests",
        description=(
            "List Overseerr requests that look failed by cross-checking status fields, since "
            "Overseerr filter parameters are limited."
        ),
        args_model=OverseerrFailedRequestsArgs,
    )(overseerr_failed_requests)
    registry.register(
        name="media_fault_timeline",
        description=(
            "Merge recent Tautulli history and Overseerr failed requests into a single "
            "timeline by timestamp and source."
        ),
        args_model=FaultTimelineArgs,
    )(fault_timeline)


def tautulli_recent_history(arguments: BaseModel) -> ToolResult:
    args = TautulliHistoryArgs.model_validate(arguments)
    return _tautulli_call({"cmd": "get_history", "length": args.length})


def tautulli_status(arguments: BaseModel) -> ToolResult:
    TautulliHistoryArgs.model_validate(arguments)
    return _tautulli_call({"cmd": "status"})


def overseerr_requests(arguments: BaseModel) -> ToolResult:
    args = OverseerrRequestsArgs.model_validate(arguments)
    params: dict[str, Any] = {"take": args.take}
    if args.filter:
        params["filter"] = args.filter
    return _overseerr_call("/api/v1/request", params=params)


def overseerr_failed_requests(arguments: BaseModel) -> ToolResult:
    args = OverseerrFailedRequestsArgs.model_validate(arguments)
    result = _overseerr_call("/api/v1/request", params={"take": args.take})
    if not result.success:
        return result
    records = _overseerr_results(result.data)
    failed = [_overseerr_summary(row) for row in records if _looks_failed(row)]
    return ToolResult(
        success=True,
        data={"count": len(failed), "requests": failed},
    )


def fault_timeline(arguments: BaseModel) -> ToolResult:
    args = FaultTimelineArgs.model_validate(arguments)
    events: list[dict[str, Any]] = []
    settings = get_settings()
    sources: list[str] = []

    if settings.tautulli.configured:
        history = _tautulli_call({"cmd": "get_history", "length": args.tautulli_length})
        sources.append("tautulli")
        if history.success:
            events.extend(_tautulli_events(history.data))

    if settings.overseerr.configured:
        sources.append("overseerr")
        failed = overseerr_failed_requests(OverseerrFailedRequestsArgs(take=args.overseerr_take))
        if failed.success and isinstance(failed.data, dict):
            for row in failed.data.get("requests", []):
                events.append(
                    {
                        "source": "overseerr",
                        "timestamp": row.get("updated_at") or row.get("created_at"),
                        "type": "request_failed",
                        "title": row.get("media_title"),
                        "status": row.get("status"),
                        "media_status": row.get("media_status"),
                        "user": row.get("requested_by"),
                    }
                )

    events = [event for event in events if event.get("timestamp")]
    events.sort(key=lambda event: str(event.get("timestamp")), reverse=True)
    return ToolResult(
        success=True,
        data={"sources_queried": sources, "event_count": len(events), "events": events},
    )


def _tautulli_call(params: dict[str, Any]) -> ToolResult:
    settings = get_settings()
    if not settings.tautulli.configured:
        return ToolResult(success=False, error="Tautulli integration is not configured.")
    api_key = settings.tautulli_api_key.get_secret_value() if settings.tautulli_api_key else ""
    merged: dict[str, Any] = {"apikey": api_key, **params}
    try:
        with _tautulli_client(settings) as client:
            response = client.get("/api/v2", params=merged)
            response.raise_for_status()
            return ToolResult(success=True, data=response.json())
    except httpx.HTTPError as exc:
        return ToolResult(success=False, error=f"Tautulli request failed: {exc}")


def _tautulli_client(settings: AppSettings) -> httpx.Client:
    return httpx.Client(base_url=str(settings.tautulli_base_url), timeout=10)


def _overseerr_call(path: str, *, params: dict[str, Any] | None = None) -> ToolResult:
    settings = get_settings()
    if not settings.overseerr.configured:
        return ToolResult(success=False, error="Overseerr integration is not configured.")
    try:
        with _overseerr_client(settings.overseerr) as client:
            response = client.get(path, params=params)
            response.raise_for_status()
            return ToolResult(success=True, data=response.json())
    except httpx.HTTPError as exc:
        return ToolResult(success=False, error=f"Overseerr request failed: {exc}")


def _overseerr_client(integration: IntegrationSettings) -> httpx.Client:
    api_key = integration.api_key.get_secret_value() if integration.api_key else ""
    return httpx.Client(
        base_url=str(integration.base_url),
        headers={"X-Api-Key": api_key, "Accept": "application/json"},
        timeout=10,
    )


def _overseerr_results(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        results = data.get("results")
        if isinstance(results, list):
            return [row for row in results if isinstance(row, dict)]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _looks_failed(row: dict[str, Any]) -> bool:
    status = row.get("status")
    media = row.get("media")
    media_status = media.get("status") if isinstance(media, dict) else None
    if status in _OVERSEERR_FAILURE_STATUSES:
        return True
    return media_status in _OVERSEERR_FAILURE_STATUSES


def _overseerr_summary(row: dict[str, Any]) -> dict[str, Any]:
    media_value = row.get("media")
    media: dict[str, Any] = media_value if isinstance(media_value, dict) else {}
    requested_value = row.get("requestedBy")
    requested_by: dict[str, Any] = requested_value if isinstance(requested_value, dict) else {}
    return {
        "id": row.get("id"),
        "status": row.get("status"),
        "media_status": media.get("status"),
        "media_title": media.get("title") or media.get("originalTitle"),
        "media_type": row.get("type") or media.get("mediaType"),
        "created_at": row.get("createdAt"),
        "updated_at": row.get("updatedAt"),
        "requested_by": requested_by.get("displayName") or requested_by.get("username"),
    }


def _tautulli_events(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    response = data.get("response")
    if not isinstance(response, dict):
        return []
    payload = response.get("data")
    rows: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        candidates = payload.get("data")
        if isinstance(candidates, list):
            rows = [row for row in candidates if isinstance(row, dict)]
    events: list[dict[str, Any]] = []
    for row in rows:
        events.append(
            {
                "source": "tautulli",
                "timestamp": row.get("date") or row.get("stopped") or row.get("started"),
                "type": "playback",
                "title": row.get("full_title") or row.get("title"),
                "user": row.get("user"),
                "watched_status": row.get("watched_status"),
                "transcode_decision": row.get("transcode_decision"),
            }
        )
    return events
