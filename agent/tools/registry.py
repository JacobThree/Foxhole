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
    from schemas.python.events import IntegrationCapabilities

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
        "dhcp",
        "dns",
        "lan",
        "mac",
        "network",
        "pihole",
        "pi-hole",
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
    ) -> None:
        self.name = name
        self.description = description
        self.args_model = args_model
        self.handler = handler
        self.safety = safety

    def schema(self) -> dict[str, Any]:
        return self.args_model.model_json_schema()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.schema(),
            safety=self.safety,
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
    ) -> Callable[[ToolHandler], ToolHandler]:
        def decorator(handler: ToolHandler) -> ToolHandler:
            self.add(
                RegisteredTool(
                    name=name,
                    description=description,
                    args_model=args_model,
                    handler=handler,
                    safety=safety,
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
    "portainer": ("portainer_",),
    "pihole": ("network_",),
    "unbound": ("network_",),
    "security": ("security_",),
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
    from tools.docker_tool import register_tools as register_docker_tools
    from tools.network_tool import register_tools as register_network_tools
    from tools.observability_tool import register_tools as register_observability_tools
    from tools.plex_tool import register_tools as register_plex_tools
    from tools.portainer_tool import register_tools as register_portainer_tools
    from tools.proxmox_tool import register_tools as register_proxmox_tools
    from tools.security_tool import register_tools as register_security_tools

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
    if status.get("pihole") or status.get("unbound"):
        register_network_tools(registry)

    register_security_tools(registry)

    if registry is default_registry:
        _builtins_registered = True


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
                    )
                    for tool in visible_tools
                ],
            )
        )
    return capabilities


def _stage_behavior(safety: ToolSafety) -> str:
    if safety is ToolSafety.READ_ONLY:
        return "Read-only in all write-safety stages."
    if safety is ToolSafety.REQUIRES_CONFIRMATION:
        return "Denied in Stage 1, confirmation-gated in Stage 2, policy-gated in Stage 3."
    return "Denied in Stage 1, confirmation-gated in Stage 2, allowed by policy in Stage 3."
