from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from agent.settings import AppSettings, IntegrationSettings, get_settings
from agent.tools.base import ToolResult, ToolSafety
from agent.tools.registry import ToolRegistry
from schemas.python.arr import (
    ArrDownloadClientsArgs,
    ArrHealthArgs,
    ArrImportDiagnosisArgs,
    ArrQualityProfilesArgs,
    ArrQualityProfileUpdateArgs,
    ArrQueueArgs,
    ArrQueueItemActionArgs,
    ArrRootFoldersArgs,
    ArrService,
)


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="arr_queue",
        description="List the Sonarr or Radarr download queue with warnings and status messages.",
        args_model=ArrQueueArgs,
    )(queue)
    registry.register(
        name="arr_health",
        description="Read Sonarr or Radarr health checks.",
        args_model=ArrHealthArgs,
    )(health)
    registry.register(
        name="arr_root_folders",
        description="List configured root folders for Sonarr or Radarr.",
        args_model=ArrRootFoldersArgs,
    )(root_folders)
    registry.register(
        name="arr_download_clients",
        description="List configured download clients for Sonarr or Radarr.",
        args_model=ArrDownloadClientsArgs,
    )(download_clients)
    registry.register(
        name="arr_quality_profiles",
        description="List Sonarr or Radarr quality profiles.",
        args_model=ArrQualityProfilesArgs,
    )(quality_profiles)
    registry.register(
        name="arr_import_diagnosis",
        description=(
            "Diagnose Sonarr/Radarr import failures by comparing queue output paths against "
            "configured root folders to detect Docker volume mismatches."
        ),
        args_model=ArrImportDiagnosisArgs,
    )(import_diagnosis)


def queue(arguments: BaseModel) -> ToolResult:
    args = ArrQueueArgs.model_validate(arguments)
    return _request_json(
        args.service,
        "GET",
        "/api/v3/queue",
        params={"pageSize": args.page_size, "includeUnknownSeriesItems": "true"},
    )


def health(arguments: BaseModel) -> ToolResult:
    args = ArrHealthArgs.model_validate(arguments)
    return _request_json(args.service, "GET", "/api/v3/health")


def root_folders(arguments: BaseModel) -> ToolResult:
    args = ArrRootFoldersArgs.model_validate(arguments)
    return _request_json(args.service, "GET", "/api/v3/rootfolder")


def download_clients(arguments: BaseModel) -> ToolResult:
    args = ArrDownloadClientsArgs.model_validate(arguments)
    return _request_json(args.service, "GET", "/api/v3/downloadclient")


def quality_profiles(arguments: BaseModel) -> ToolResult:
    args = ArrQualityProfilesArgs.model_validate(arguments)
    return _request_json(args.service, "GET", "/api/v3/qualityprofile")


def import_diagnosis(arguments: BaseModel) -> ToolResult:
    args = ArrImportDiagnosisArgs.model_validate(arguments)
    queue_result = queue(ArrQueueArgs(service=args.service, page_size=args.page_size))
    if not queue_result.success:
        return queue_result
    roots_result = root_folders(ArrRootFoldersArgs(service=args.service))
    if not roots_result.success:
        return roots_result

    queue_items = _queue_records(queue_result.data)
    root_paths = _root_paths(roots_result.data)
    mismatches: list[dict[str, Any]] = []
    for item in queue_items:
        output_path = _output_path(item)
        if not output_path:
            continue
        if not any(_path_under(output_path, root) for root in root_paths):
            mismatches.append(
                {
                    "title": item.get("title"),
                    "queue_id": item.get("id"),
                    "output_path": output_path,
                    "expected_roots": root_paths,
                    "status": item.get("status"),
                    "tracked_messages": _status_messages(item),
                }
            )
    return ToolResult(
        success=True,
        data={
            "service": args.service.value,
            "queue_size": len(queue_items),
            "root_folders": root_paths,
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
        },
    )


def update_quality_profile(arguments: BaseModel) -> ToolResult:
    args = ArrQualityProfileUpdateArgs.model_validate(arguments)
    current = _request_json(args.service, "GET", f"/api/v3/qualityprofile/{args.profile_id}")
    if not current.success or not isinstance(current.data, dict):
        return current
    before = current.data
    payload = dict(before)
    payload["name"] = args.name
    payload["upgradeAllowed"] = args.upgrade_allowed
    updated = _request_json(
        args.service, "PUT", f"/api/v3/qualityprofile/{args.profile_id}", json=payload
    )
    if not updated.success:
        return updated
    return ToolResult(
        success=True,
        data={
            "service": args.service.value,
            "profile_id": args.profile_id,
            "before": {"name": before.get("name"), "upgradeAllowed": before.get("upgradeAllowed")},
            "after": {"name": args.name, "upgradeAllowed": args.upgrade_allowed},
            "raw_after": updated.data,
        },
    )


def queue_item_action(arguments: BaseModel) -> ToolResult:
    args = ArrQueueItemActionArgs.model_validate(arguments)
    return _request_json(
        args.service,
        "DELETE",
        f"/api/v3/queue/{args.queue_id}",
        params={
            "removeFromClient": str(args.remove_from_client).lower(),
            "blocklist": str(args.blocklist).lower(),
        },
    )


def register_write_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="arr_update_quality_profile",
        description=(
            "Rename a Sonarr or Radarr quality profile and toggle upgrade_allowed. "
            "Requires confirmation and shows a before/after diff."
        ),
        args_model=ArrQualityProfileUpdateArgs,
        safety=ToolSafety.REQUIRES_CONFIRMATION,
    )(update_quality_profile)
    registry.register(
        name="arr_queue_item_action",
        description=(
            "Remove a specific Sonarr/Radarr queue item and optionally blocklist the release. "
            "Confirmation-gated."
        ),
        args_model=ArrQueueItemActionArgs,
        safety=ToolSafety.REQUIRES_CONFIRMATION,
    )(queue_item_action)


def _request_json(
    service: ArrService,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> ToolResult:
    settings = get_settings()
    integration = _integration_for(settings, service)
    if not integration.configured:
        return ToolResult(success=False, error=f"{service.value} integration is not configured.")
    try:
        with _client(integration) as client:
            response = client.request(method, path, params=params, json=json)
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return ToolResult(success=True, data={})
            return ToolResult(success=True, data=response.json())
    except httpx.HTTPError as exc:
        return ToolResult(success=False, error=f"{service.value} request failed: {exc}")


def _integration_for(settings: AppSettings, service: ArrService) -> IntegrationSettings:
    return settings.sonarr if service is ArrService.SONARR else settings.radarr


def _client(integration: IntegrationSettings) -> httpx.Client:
    api_key = integration.api_key.get_secret_value() if integration.api_key else ""
    return httpx.Client(
        base_url=str(integration.base_url),
        headers={"X-Api-Key": api_key, "Accept": "application/json"},
        timeout=10,
    )


def _queue_records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        records = data.get("records")
        if isinstance(records, list):
            return [r for r in records if isinstance(r, dict)]
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    return []


def _root_paths(data: Any) -> list[str]:
    if not isinstance(data, list):
        return []
    paths: list[str] = []
    for row in data:
        if isinstance(row, dict):
            path = row.get("path")
            if isinstance(path, str) and path:
                paths.append(path.rstrip("/"))
    return paths


def _output_path(item: dict[str, Any]) -> str | None:
    output = item.get("outputPath")
    if isinstance(output, str) and output:
        return output
    nested = item.get("statusMessages")
    if isinstance(nested, list):
        for message in nested:
            if isinstance(message, dict):
                candidate = message.get("title")
                if isinstance(candidate, str) and candidate.startswith("/"):
                    return candidate
    return None


def _status_messages(item: dict[str, Any]) -> list[str]:
    messages = item.get("statusMessages")
    out: list[str] = []
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict):
                for value in message.get("messages", []) or []:
                    if isinstance(value, str):
                        out.append(value)
    return out


def _path_under(child: str, parent: str) -> bool:
    normalized_child = child.rstrip("/")
    normalized_parent = parent.rstrip("/")
    if not normalized_parent:
        return False
    return normalized_child == normalized_parent or normalized_child.startswith(
        normalized_parent + "/"
    )
