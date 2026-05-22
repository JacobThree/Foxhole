from __future__ import annotations

import importlib
from typing import Any

from pydantic import BaseModel

from agent.settings import AppSettings, get_settings
from agent.tools.base import ToolResult, ToolSafety
from agent.tools.registry import ToolRegistry
from schemas.python.proxmox import (
    ProxmoxBackupJobsArgs,
    ProxmoxInventoryArgs,
    ProxmoxMigrateLxcArgs,
    ProxmoxNodeStatusArgs,
    ProxmoxStorageArgs,
)


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="proxmox_node_status",
        description="Read Proxmox node status with audit-only API token privileges.",
        args_model=ProxmoxNodeStatusArgs,
    )(node_status)
    registry.register(
        name="proxmox_inventory",
        description="List Proxmox LXC and VM inventory with audit-only API token privileges.",
        args_model=ProxmoxInventoryArgs,
    )(inventory)
    registry.register(
        name="proxmox_storage_usage",
        description=(
            "Read Proxmox storage usage including used percentage, used GB, total GB, "
            "and type."
        ),
        args_model=ProxmoxStorageArgs,
    )(storage_usage)
    registry.register(
        name="proxmox_backup_jobs",
        description="Read Proxmox backup job visibility and last-run state.",
        args_model=ProxmoxBackupJobsArgs,
    )(backup_jobs)
    registry.register(
        name="proxmox_migrate_lxc",
        description="Migrate a Proxmox LXC after write-policy confirmation.",
        args_model=ProxmoxMigrateLxcArgs,
        safety=ToolSafety.REQUIRES_CONFIRMATION,
    )(migrate_lxc)


def node_status(arguments: BaseModel) -> ToolResult:
    args = ProxmoxNodeStatusArgs.model_validate(arguments)
    try:
        client = _proxmox_client()
        nodes = _selected_nodes(client, args.node)
        return ToolResult(
            success=True,
            data=[{"node": node, "status": client.nodes(node).status.get()} for node in nodes],
        )
    except Exception as exc:
        return ToolResult(success=False, error=f"Proxmox request failed: {exc}")


def inventory(arguments: BaseModel) -> ToolResult:
    args = ProxmoxInventoryArgs.model_validate(arguments)
    try:
        client = _proxmox_client()
        nodes = _selected_nodes(client, args.node)
        rows: list[dict[str, Any]] = []
        for node in nodes:
            if args.include_lxcs:
                rows.extend(_inventory_rows(node, "lxc", client.nodes(node).lxc.get()))
            if args.include_vms:
                rows.extend(_inventory_rows(node, "qemu", client.nodes(node).qemu.get()))
        return ToolResult(success=True, data=rows)
    except Exception as exc:
        return ToolResult(success=False, error=f"Proxmox request failed: {exc}")


def storage_usage(arguments: BaseModel) -> ToolResult:
    args = ProxmoxStorageArgs.model_validate(arguments)
    try:
        client = _proxmox_client()
        rows: list[dict[str, Any]] = []
        for node in _selected_nodes(client, args.node):
            for storage in client.nodes(node).storage.get():
                storage_id = str(storage.get("storage", ""))
                status = client.nodes(node).storage(storage_id).status.get()
                rows.append(_storage_row(node, storage, status))
        return ToolResult(success=True, data=rows)
    except Exception as exc:
        return ToolResult(success=False, error=f"Proxmox request failed: {exc}")


def backup_jobs(arguments: BaseModel) -> ToolResult:
    ProxmoxBackupJobsArgs.model_validate(arguments)
    try:
        jobs = _proxmox_client().cluster.backup.get()
        return ToolResult(success=True, data=[_backup_job_row(job) for job in jobs])
    except Exception as exc:
        return ToolResult(success=False, error=f"Proxmox request failed: {exc}")


def migrate_lxc(arguments: BaseModel) -> ToolResult:
    args = ProxmoxMigrateLxcArgs.model_validate(arguments)
    try:
        task_id = (
            _proxmox_client()
            .nodes(args.source_node)
            .lxc(args.vmid)
            .migrate.post(target=args.target_node, online=1 if args.online else 0)
        )
        return ToolResult(
            success=True,
            data={
                "vmid": args.vmid,
                "source_node": args.source_node,
                "target_node": args.target_node,
                "online": args.online,
                "task_id": task_id,
            },
        )
    except Exception as exc:
        return ToolResult(success=False, error=f"Proxmox migration failed: {exc}")


def _proxmox_client() -> Any:
    settings = get_settings()
    if not settings.proxmox.configured:
        raise RuntimeError("Proxmox integration is not configured.")
    return build_proxmox_client(settings)


def build_proxmox_client(settings: AppSettings) -> Any:
    token_id = settings.proxmox_token_id.get_secret_value() if settings.proxmox_token_id else ""
    token_secret = (
        settings.proxmox_token_secret.get_secret_value() if settings.proxmox_token_secret else ""
    )
    user, token_name = _split_token_id(token_id)
    proxmoxer = importlib.import_module("proxmoxer")
    return proxmoxer.ProxmoxAPI(
        settings.proxmox_host,
        user=user,
        token_name=token_name,
        token_value=token_secret,
        verify_ssl=settings.proxmox_verify_ssl,
    )


def _selected_nodes(client: Any, node: str | None) -> list[str]:
    if node is not None:
        return [node]
    return [str(item["node"]) for item in client.nodes.get()]


def _inventory_rows(
    node: str, resource_type: str, values: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {
            "node": node,
            "type": resource_type,
            "vmid": value.get("vmid"),
            "name": value.get("name"),
            "status": value.get("status"),
            "cpu": value.get("cpu"),
            "mem_bytes": value.get("mem"),
            "maxmem_bytes": value.get("maxmem"),
            "disk_bytes": value.get("disk"),
            "maxdisk_bytes": value.get("maxdisk"),
        }
        for value in values
    ]


def _storage_row(node: str, storage: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    used = _float(status.get("used") or storage.get("used"))
    total = _float(status.get("total") or storage.get("total"))
    used_percent = round((used / total) * 100, 2) if total > 0 else 0.0
    return {
        "node": node,
        "storage": storage.get("storage"),
        "type": storage.get("type"),
        "content": storage.get("content"),
        "enabled": storage.get("enabled", 1) == 1,
        "used_percent": used_percent,
        "used_gb": round(used / 1_073_741_824, 2),
        "total_gb": round(total / 1_073_741_824, 2),
    }


def _backup_job_row(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job.get("id"),
        "enabled": job.get("enabled", 1) == 1,
        "schedule": job.get("schedule"),
        "storage": job.get("storage"),
        "last_run_endtime": job.get("last-run-endtime") or job.get("last_run_endtime"),
        "last_run_state": job.get("last-run-state") or job.get("last_run_state"),
        "vmids": job.get("vmid"),
    }


def _split_token_id(token_id: str) -> tuple[str, str]:
    user, separator, token_name = token_id.partition("!")
    if not separator or not user or not token_name:
        raise ValueError("Proxmox token id must use the form user@realm!token-name.")
    return user, token_name


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
