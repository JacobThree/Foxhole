from __future__ import annotations

import builtins
import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from agent.tools.base import ToolResult, ToolSafety, ToolSpec

ToolHandler = Callable[[BaseModel], ToolResult | Awaitable[ToolResult]]


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

    def schemas(self) -> builtins.list[dict[str, Any]]:
        return [tool.as_openai_tool() for tool in self.list()]


default_registry = ToolRegistry()
_builtins_registered = False


def register_builtin_tools(registry: ToolRegistry = default_registry) -> None:
    global _builtins_registered
    if registry is default_registry and _builtins_registered:
        return

    from tools.backup_tool import register_tools as register_backup_tools
    from tools.docker_tool import register_tools as register_docker_tools
    from tools.portainer_tool import register_tools as register_portainer_tools
    from tools.proxmox_tool import register_tools as register_proxmox_tools

    register_docker_tools(registry)
    register_portainer_tools(registry)
    register_proxmox_tools(registry)
    register_backup_tools(registry)
    if registry is default_registry:
        _builtins_registered = True
