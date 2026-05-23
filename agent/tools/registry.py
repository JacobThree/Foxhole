from __future__ import annotations

import builtins
import inspect
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from agent.tools.base import ToolResult, ToolSafety, ToolSpec

if TYPE_CHECKING:
    from agent.settings import AppSettings
    from schemas.python.events import IntegrationCapabilities, IntegrationManifest

ToolHandler = Callable[[BaseModel], ToolResult | Awaitable[ToolResult]]


class ToolIntent(StrEnum):
    MEDIA = "media"
    NETWORK = "network"
    STORAGE = "storage"
    CONTAINERS = "containers"
    SECURITY = "security"


INTENT_KEYWORDS: dict[ToolIntent, tuple[str, ...]] = {
    ToolIntent.MEDIA: (
        "arr",
        "buffer",
        "download",
        "import",
        "jellyfin",
        "media",
        "movie",
        "overseerr",
        "plex",
        "radarr",
        "request",
        "sonarr",
        "tautulli",
        "transcode",
        "tv",
    ),
    ToolIntent.NETWORK: (
        "client",
        "caddy",
        "dhcp",
        "dns",
        "lan",
        "mac",
        "network",
        "pihole",
        "pi-hole",
        "proxy",
        "query",
        "rogue",
        "subnet",
        "unbound",
        "wifi",
    ),
    ToolIntent.STORAGE: ("backup", "disk", "pbs", "proxmox", "storage", "zfs"),
    ToolIntent.CONTAINERS: (
        "container",
        "docker",
        "image",
        "portainer",
        "restart loop",
        "socket",
    ),
    ToolIntent.SECURITY: ("privileged", "risk", "security", "vulnerability"),
}

INTENT_TOOL_PREFIXES: dict[ToolIntent, tuple[str, ...]] = {
    ToolIntent.MEDIA: (
        "plex_",
        "arr_",
        "tautulli_",
        "overseerr_",
        "media_",
        "docker_",
        "backup_",
    ),
    ToolIntent.NETWORK: ("network_", "security_"),
    ToolIntent.STORAGE: ("backup_", "proxmox_", "docker_"),
    ToolIntent.CONTAINERS: ("docker_", "portainer_", "security_"),
    ToolIntent.SECURITY: ("security_", "docker_", "network_"),
}


class RegisteredTool:
    def __init__(
        self,
        *,
        name: str,
        description: str,
        args_model: type[BaseModel],
        handler: ToolHandler,
        safety: ToolSafety = ToolSafety.READ_ONLY,
        integration: str | None = None,
        capability_ids: list[str] | None = None,
        category: str | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.args_model = args_model
        self.handler = handler
        self.safety = safety
        self.integration = integration or integration_for_tool(name)
        self.capability_ids = capability_ids or capability_ids_for_tool(name, self.safety)
        self.category = category or ("read" if self.safety is ToolSafety.READ_ONLY else "write")

    def schema(self) -> dict[str, Any]:
        return self.args_model.model_json_schema()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.schema(),
            safety=self.safety,
            integration=self.integration,
            capability_ids=self.capability_ids,
            category=self.category,
        )

    def as_openai_tool(self) -> dict[str, Any]:
        return self.spec().as_openai_tool()

    async def run(self, arguments: BaseModel) -> ToolResult:
        started = time.perf_counter()
        result = self.handler(arguments)
        if inspect.isawaitable(result):
            result = await result
        result.duration_ms = round((time.perf_counter() - started) * 1000, 3)
        return result


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        args_model: type[BaseModel],
        safety: ToolSafety = ToolSafety.READ_ONLY,
        integration: str | None = None,
        capability_ids: list[str] | None = None,
        category: str | None = None,
    ) -> Callable[[ToolHandler], ToolHandler]:
        def decorator(handler: ToolHandler) -> ToolHandler:
            self.add(
                RegisteredTool(
                    name=name,
                    description=description,
                    args_model=args_model,
                    handler=handler,
                    safety=safety,
                    integration=integration,
                    capability_ids=capability_ids,
                    category=category,
                )
            )
            return handler

        return decorator

    def add(self, tool: RegisteredTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc

    def list(self) -> builtins.list[RegisteredTool]:
        return list(self._tools.values())

    def list_for_message(self, message: str) -> builtins.list[RegisteredTool]:
        intents = classify_tool_intents(message)
        if not intents:
            return [tool for tool in self.list() if tool.safety is ToolSafety.READ_ONLY]

        prefixes = tuple(
            prefix for intent in intents for prefix in INTENT_TOOL_PREFIXES.get(intent, ())
        )
        selected = [tool for tool in self.list() if tool.name.startswith(prefixes)]
        if selected:
            return selected
        return [tool for tool in self.list() if tool.safety is ToolSafety.READ_ONLY]

    def schemas(
        self, tools: builtins.list[RegisteredTool] | None = None
    ) -> builtins.list[dict[str, Any]]:
        selected_tools = self.list() if tools is None else tools
        return [tool.as_openai_tool() for tool in selected_tools]

    def schemas_for_message(self, message: str) -> builtins.list[dict[str, Any]]:
        return self.schemas(self.list_for_message(message))


def classify_tool_intents(message: str) -> set[ToolIntent]:
    normalized = message.casefold()
    return {
        intent
        for intent, keywords in INTENT_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    }


default_registry = ToolRegistry()
_builtins_registered = False
INTEGRATION_TOOL_PREFIXES = {
    "docker": ("docker_",),
    "proxmox": ("proxmox_", "backup_"),
    "plex": ("plex_",),
    "sonarr": ("arr_",),
    "radarr": ("arr_",),
    "tautulli": ("tautulli_", "media_"),
    "overseerr": ("overseerr_", "media_"),
    "uptime_kuma": ("uptime_kuma_",),
    "caddy": ("caddy_",),
    "portainer": ("portainer_",),
    "pihole": ("network_",),
    "unbound": ("network_",),
    "security": ("security_",),
}

TOOL_CAPABILITY_IDS: dict[str, tuple[str, ...]] = {
    "docker_list_containers": ("containers.list",),
    "docker_inspect_container": ("containers.inspect",),
    "docker_read_logs": ("containers.logs.read",),
    "docker_detect_restart_loops": ("containers.health.read",),
    "docker_container_action": ("containers.lifecycle.confirmed",),
    "portainer_list_endpoints": ("containers.portainer.endpoints.read",),
    "portainer_list_stacks": ("containers.portainer.stacks.read",),
    "portainer_stack_details": ("containers.portainer.stacks.read",),
    "portainer_redeploy_stack": ("containers.portainer.redeploy.confirmed",),
    "proxmox_node_status": ("virtualization.nodes.read",),
    "proxmox_inventory": ("virtualization.inventory.read",),
    "proxmox_storage_usage": ("storage.usage.read",),
    "proxmox_backup_jobs": ("backups.jobs.read",),
    "proxmox_migrate_lxc": ("virtualization.lxc.migrate.confirmed",),
    "backup_storage_health": ("backups.health.read", "storage.health.read"),
    "plex_active_sessions": ("media.sessions.read",),
    "plex_transcode_status": ("media.transcode.read",),
    "plex_analyze_logs": ("media.logs.read",),
    "plex_buffering_diagnosis": ("media.buffering.diagnose",),
    "plex_debug_guidance": ("media.debug.read",),
    "arr_queue": ("media.arr.queue.read",),
    "arr_health": ("media.arr.health.read",),
    "arr_root_folders": ("media.arr.root_folders.read",),
    "arr_download_clients": ("media.arr.download_clients.read",),
    "arr_quality_profiles": ("media.arr.quality_profiles.read",),
    "arr_import_diagnosis": ("media.arr.imports.diagnose",),
    "arr_update_quality_profile": ("media.arr.quality_profiles.confirmed",),
    "arr_queue_item_action": ("media.arr.queue.confirmed",),
    "tautulli_recent_history": ("media.tautulli.history.read",),
    "tautulli_status": ("media.tautulli.status.read",),
    "overseerr_requests": ("media.overseerr.requests.read",),
    "overseerr_failed_requests": ("media.overseerr.failures.read",),
    "media_fault_timeline": ("media.timeline.read",),
    "uptime_kuma_monitor_status": ("monitoring.monitors.read",),
    "uptime_kuma_recent_failures": ("monitoring.failures.read",),
    "caddy_list_routes": ("reverse_proxy.routes.read", "reverse_proxy.upstreams.read"),
    "caddy_route_diagnosis": ("reverse_proxy.routes.diagnose",),
    "pihole_summary": ("dns.summary.read",),
    "pihole_recent_blocked": ("dns.blocked.read",),
    "pihole_recent_queries": ("dns.queries.read",),
    "unbound_stats": ("dns.resolver.stats.read",),
    "network_scan": ("network.scan.read",),
    "network_unknown_devices": ("network.devices.read",),
    "security_posture": ("security.posture.read",),
}

INTEGRATION_MANIFEST_INFO: dict[str, dict[str, Any]] = {
    "docker": {
        "name": "Docker",
        "category": "containers",
        "required_config": ["docker_socket_proxy_url"],
        "resource_uris": ["foxhole://docker/containers"],
        "event_types": ["scheduled_check.container_health"],
        "diagnostic_bundles": ["container_health"],
    },
    "portainer": {
        "name": "Portainer",
        "category": "containers",
        "required_config": ["portainer_base_url", "portainer_credentials"],
        "resource_uris": ["foxhole://portainer/stacks"],
        "event_types": ["tool.portainer"],
        "diagnostic_bundles": [],
    },
    "proxmox": {
        "name": "Proxmox VE",
        "category": "virtualization",
        "required_config": ["proxmox_host", "proxmox_token_id", "proxmox_token_secret"],
        "resource_uris": ["foxhole://proxmox/nodes", "foxhole://proxmox/storage"],
        "event_types": ["scheduled_check.storage_thresholds"],
        "diagnostic_bundles": ["storage_thresholds"],
    },
    "plex": {
        "name": "Plex",
        "category": "media",
        "required_config": ["plex_base_url", "plex_token"],
        "optional_config": ["plex_log_path"],
        "resource_uris": ["foxhole://plex/sessions", "foxhole://plex/logs"],
        "event_types": ["scheduled_check.plex_db_health"],
        "diagnostic_bundles": ["plex_db_health"],
    },
    "sonarr": {
        "name": "Sonarr",
        "category": "media",
        "required_config": ["sonarr_base_url", "sonarr_api_key"],
        "resource_uris": ["foxhole://sonarr/queue", "foxhole://sonarr/health"],
        "event_types": ["scheduled_check.arr_imports"],
        "diagnostic_bundles": ["arr_imports"],
    },
    "radarr": {
        "name": "Radarr",
        "category": "media",
        "required_config": ["radarr_base_url", "radarr_api_key"],
        "resource_uris": ["foxhole://radarr/queue", "foxhole://radarr/health"],
        "event_types": ["scheduled_check.arr_imports"],
        "diagnostic_bundles": ["arr_imports"],
    },
    "tautulli": {
        "name": "Tautulli",
        "category": "media",
        "required_config": ["tautulli_base_url", "tautulli_api_key"],
        "resource_uris": ["foxhole://tautulli/history"],
        "event_types": ["tool.tautulli"],
        "diagnostic_bundles": [],
    },
    "overseerr": {
        "name": "Overseerr",
        "category": "media",
        "required_config": ["overseerr_base_url", "overseerr_api_key"],
        "resource_uris": ["foxhole://overseerr/requests"],
        "event_types": ["tool.overseerr"],
        "diagnostic_bundles": [],
    },
    "uptime_kuma": {
        "name": "Uptime Kuma",
        "category": "monitoring",
        "required_config": ["uptime_kuma_base_url", "uptime_kuma_api_token"],
        "resource_uris": ["foxhole://monitoring/uptime-kuma/monitors"],
        "event_types": ["scheduled_check.uptime_kuma_monitors"],
        "diagnostic_bundles": ["uptime_kuma_monitors"],
    },
    "caddy": {
        "name": "Caddy",
        "category": "reverse_proxy",
        "required_config": ["caddy_config_or_admin_api"],
        "optional_config": ["caddy_config_path", "caddy_admin_api_url"],
        "resource_uris": ["foxhole://reverse-proxy/caddy/routes"],
        "event_types": ["tool.caddy"],
        "diagnostic_bundles": ["caddy_routes"],
    },
    "pihole": {
        "name": "Pi-hole",
        "category": "dns",
        "required_config": ["pihole_base_url", "pihole_api_token"],
        "resource_uris": ["foxhole://dns/pihole/summary"],
        "event_types": ["scheduled_check.rogue_macs"],
        "diagnostic_bundles": ["rogue_macs"],
    },
    "unbound": {
        "name": "Unbound",
        "category": "dns",
        "required_config": ["unbound_host"],
        "optional_config": ["unbound_port"],
        "resource_uris": ["foxhole://dns/unbound/stats"],
        "event_types": ["scheduled_check.rogue_macs"],
        "diagnostic_bundles": ["rogue_macs"],
    },
    "security": {
        "name": "Security posture",
        "category": "security",
        "required_config": [],
        "resource_uris": ["foxhole://security/posture"],
        "event_types": ["scheduled_check.container_health"],
        "diagnostic_bundles": ["container_health"],
    },
}


def register_builtin_tools(
    registry: ToolRegistry = default_registry, settings: AppSettings | None = None
) -> None:
    global _builtins_registered
    if registry is default_registry and _builtins_registered:
        return

    from agent.settings import get_settings
    from tools.arr_tool import register_tools as register_arr_tools
    from tools.arr_tool import register_write_tools as register_arr_write_tools
    from tools.backup_tool import register_tools as register_backup_tools
    from tools.caddy_tool import register_tools as register_caddy_tools
    from tools.docker_tool import register_tools as register_docker_tools
    from tools.network_tool import register_tools as register_network_tools
    from tools.observability_tool import register_tools as register_observability_tools
    from tools.plex_tool import register_tools as register_plex_tools
    from tools.portainer_tool import register_tools as register_portainer_tools
    from tools.proxmox_tool import register_tools as register_proxmox_tools
    from tools.security_tool import register_tools as register_security_tools
    from tools.uptime_kuma_tool import register_tools as register_uptime_kuma_tools

    status = (settings or get_settings()).integration_status()

    if status.get("docker"):
        register_docker_tools(registry)
    if status.get("portainer"):
        register_portainer_tools(registry)
    if status.get("proxmox"):
        register_proxmox_tools(registry)
        register_backup_tools(registry)
    if status.get("plex"):
        register_plex_tools(registry)
    if status.get("sonarr") or status.get("radarr"):
        register_arr_tools(registry)
        register_arr_write_tools(registry)
    if status.get("tautulli") or status.get("overseerr"):
        register_observability_tools(registry)
    if status.get("uptime_kuma"):
        register_uptime_kuma_tools(registry)
    if status.get("caddy"):
        register_caddy_tools(registry)
    if status.get("pihole") or status.get("unbound"):
        register_network_tools(registry)

    register_security_tools(registry)

    if registry is default_registry:
        _builtins_registered = True


def integration_for_tool(tool_name: str) -> str | None:
    for integration, prefixes in INTEGRATION_TOOL_PREFIXES.items():
        if tool_name.startswith(prefixes):
            return integration
    return None


def capability_ids_for_tool(tool_name: str, safety: ToolSafety) -> list[str]:
    explicit = TOOL_CAPABILITY_IDS.get(tool_name)
    if explicit:
        return list(explicit)
    integration = integration_for_tool(tool_name) or "tool"
    action = tool_name
    for prefix in INTEGRATION_TOOL_PREFIXES.get(integration, ()):
        if action.startswith(prefix):
            action = action.removeprefix(prefix)
            break
    suffix = "read" if safety is ToolSafety.READ_ONLY else "confirmed"
    return [f"{integration}.{action}.{suffix}"]


def integration_capabilities(
    settings: AppSettings, registry: ToolRegistry
) -> list[IntegrationCapabilities]:
    from schemas.python.events import IntegrationCapabilities, ToolCapability

    details = settings.integration_details()
    details["security"] = {
        "enabled": True,
        "configured": True,
        "missing_configuration": [],
    }

    capabilities: list[IntegrationCapabilities] = []
    for integration, detail in details.items():
        prefixes = INTEGRATION_TOOL_PREFIXES.get(integration, ())
        configured = bool(detail["configured"])
        visible_tools = [
            tool
            for tool in registry.list()
            if configured and any(tool.name.startswith(prefix) for prefix in prefixes)
        ]
        capabilities.append(
            IntegrationCapabilities(
                integration=integration,
                enabled=bool(detail["enabled"]),
                configured=configured,
                missing_configuration=list(detail["missing_configuration"]),
                capabilities=[
                    ToolCapability(
                        tool_name=tool.name,
                        description=tool.description,
                        safety=tool.safety.value,
                        stage_behavior=_stage_behavior(tool.safety),
                        integration=tool.integration or integration,
                        category=tool.category,
                        capability_ids=tool.capability_ids,
                    )
                    for tool in visible_tools
                ],
            )
        )
    return capabilities


def integration_manifests(
    settings: AppSettings, registry: ToolRegistry
) -> list[IntegrationManifest]:
    from schemas.python.events import IntegrationManifest, ManifestTool

    capabilities = {
        item.integration: item for item in integration_capabilities(settings, registry)
    }
    manifests: list[IntegrationManifest] = []
    for integration, capability_group in capabilities.items():
        info = INTEGRATION_MANIFEST_INFO.get(integration, {})
        tools = [
            tool
            for tool in registry.list()
            if tool.integration == integration
            or any(
                tool.name.startswith(prefix)
                for prefix in INTEGRATION_TOOL_PREFIXES.get(integration, ())
            )
        ]
        manifests.append(
            IntegrationManifest(
                id=integration,
                name=str(info.get("name") or integration.replace("_", " ").title()),
                category=str(info.get("category") or "integration"),
                enabled=capability_group.enabled,
                configured=capability_group.configured,
                config_schema={
                    "required": list(info.get("required_config", [])),
                    "optional": list(info.get("optional_config", [])),
                    "secrets_redacted": True,
                },
                capabilities=capability_group.capabilities,
                tools=[
                    ManifestTool(
                        name=tool.name,
                        description=tool.description,
                        safety=tool.safety.value,
                        capability_ids=tool.capability_ids,
                        input_schema=tool.schema(),
                        output_schema={"type": "object", "model": "ToolResult"},
                    )
                    for tool in tools
                ],
                resource_uris=list(info.get("resource_uris", [])),
                event_types=list(info.get("event_types", [])),
                diagnostic_bundles=list(info.get("diagnostic_bundles", [])),
                safety_posture=_safety_posture(tools),
                mcp_adapter_notes=(
                    "Capability IDs, resource URIs, input schemas, and safety levels are "
                    "structured so a future MCP adapter can expose them without changing "
                    "runtime tool handlers."
                ),
            )
        )
    return manifests


def _safety_posture(tools: list[RegisteredTool]) -> str:
    if any(tool.safety is not ToolSafety.READ_ONLY for tool in tools):
        return "Includes confirmation-gated write tools; write policy still decides execution."
    return "Read-only integration; no mutation tools are exposed."


def _stage_behavior(safety: ToolSafety) -> str:
    if safety is ToolSafety.READ_ONLY:
        return "Read-only in all write-safety stages."
    if safety is ToolSafety.REQUIRES_CONFIRMATION:
        return "Denied in Stage 1, confirmation-gated in Stage 2, policy-gated in Stage 3."
    return "Denied in Stage 1, confirmation-gated in Stage 2, allowed by policy in Stage 3."
