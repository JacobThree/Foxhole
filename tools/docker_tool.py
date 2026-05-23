from __future__ import annotations

import importlib
import re
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from agent.mock_mode import MockMode
from agent.settings import get_settings
from agent.tools.base import ToolOutputMode, ToolResult, ToolSafety
from agent.tools.registry import ToolRegistry
from schemas.python.docker import (
    DockerContainerActionArgs,
    DockerContainerPort,
    DockerContainerSummary,
    DockerInspectContainerArgs,
    DockerListContainersArgs,
    DockerReadLogsArgs,
    DockerRestartLoopArgs,
)


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="docker_list_containers",
        description="List Docker containers through the read-only socket proxy.",
        args_model=DockerListContainersArgs,
    )(list_containers)
    registry.register(
        name="docker_inspect_container",
        description=(
            "Inspect a Docker container's status, health, image metadata, labels, ports, "
            "and restart count."
        ),
        args_model=DockerInspectContainerArgs,
    )(inspect_container)
    registry.register(
        name="docker_read_logs",
        description="Read bounded Docker container logs with explicit line and byte limits.",
        args_model=DockerReadLogsArgs,
    )(read_logs)
    registry.register(
        name="docker_detect_restart_loops",
        description="Find Docker containers whose restart count suggests a restart loop.",
        args_model=DockerRestartLoopArgs,
    )(detect_restart_loops)
    registry.register(
        name="docker_container_action",
        description="Start, stop, or restart a Docker container after write-policy confirmation.",
        args_model=DockerContainerActionArgs,
        safety=ToolSafety.REQUIRES_CONFIRMATION,
    )(container_action)


def list_containers(arguments: BaseModel) -> ToolResult:
    args = DockerListContainersArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("docker_list_containers", args)
    if mock_result is not None:
        return mock_result
    try:
        client = _docker_client()
        containers = client.containers.list(all=args.all)
        data = [_container_summary(container).model_dump(mode="json") for container in containers]
        return ToolResult(
            success=True,
            data=data,
        )
    except Exception as exc:
        return _docker_error_result(exc)


def inspect_container(arguments: BaseModel) -> ToolResult:
    args = DockerInspectContainerArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("docker_inspect_container", args)
    if mock_result is not None:
        return mock_result
    try:
        container = _docker_client().containers.get(args.container)
        return ToolResult(success=True, data=_container_summary(container).model_dump(mode="json"))
    except Exception as exc:
        return _docker_error_result(exc)


def read_logs(arguments: BaseModel) -> ToolResult:
    args = DockerReadLogsArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("docker_read_logs", args)
    if mock_result is not None:
        return mock_result
    try:
        container = _docker_client().containers.get(args.container)
        raw = container.logs(tail=args.lines, stdout=True, stderr=True)
        text = raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)
        encoded = text.encode()
        truncated = len(encoded) > args.max_bytes
        if truncated:
            text = encoded[-args.max_bytes :].decode(errors="replace")
        raw_line_count = len(text.splitlines())
        if args.output_mode in {ToolOutputMode.RAW, ToolOutputMode.FORENSIC}:
            return ToolResult(
                success=True,
                output_mode=args.output_mode,
                raw_data_withheld=False,
                raw_line_count=raw_line_count,
                raw_bytes=len(text.encode()),
                data={
                    "container": args.container,
                    "lines_requested": args.lines,
                    "max_bytes": args.max_bytes,
                    "truncated": truncated,
                    "logs": text,
                },
            )
        return ToolResult(
            success=True,
            output_mode=ToolOutputMode.SUMMARY,
            raw_data_withheld=True,
            raw_line_count=raw_line_count,
            raw_bytes=len(text.encode()),
            data={
                "container": args.container,
                "lines_requested": args.lines,
                "max_bytes": args.max_bytes,
                "truncated": truncated,
                "summary": _summarize_logs(text),
                "raw_logs": "withheld; request output_mode=raw or forensic for bounded raw text",
            },
        )
    except Exception as exc:
        return _docker_error_result(exc)


def detect_restart_loops(arguments: BaseModel) -> ToolResult:
    args = DockerRestartLoopArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("docker_detect_restart_loops", args)
    if mock_result is not None:
        return mock_result
    try:
        containers = _docker_client().containers.list(all=args.all)
        summaries = [_container_summary(container) for container in containers]
        loops = [
            summary.model_dump(mode="json")
            for summary in summaries
            if summary.restart_count >= args.min_restarts
            or summary.status.lower() in {"restarting", "dead"}
        ]
        return ToolResult(
            success=True,
            data={"min_restarts": args.min_restarts, "restart_loop_candidates": loops},
        )
    except Exception as exc:
        return _docker_error_result(exc)


def container_action(arguments: BaseModel) -> ToolResult:
    args = DockerContainerActionArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("docker_container_action", args)
    if mock_result is not None:
        return mock_result
    try:
        container = _docker_client().containers.get(args.container)
        old_status = _container_summary(container).model_dump(mode="json")
        if args.action == "start":
            container.start()
        elif args.action == "stop":
            container.stop(timeout=args.timeout_seconds)
        elif args.action == "restart":
            container.restart(timeout=args.timeout_seconds)
        else:
            return ToolResult(success=False, error=f"Unsupported Docker action: {args.action}")
        _reload(container)
        new_status = _container_summary(container).model_dump(mode="json")
        return ToolResult(
            success=True,
            data={
                "container": args.container,
                "action": args.action,
                "old_status": old_status,
                "resulting_status": new_status,
            },
        )
    except Exception as exc:
        return _docker_error_result(exc)


def _docker_client() -> Any:
    settings = get_settings()
    docker = importlib.import_module("docker")
    return docker.DockerClient(base_url=settings.docker_socket_proxy_url)


def _container_summary(container: Any) -> DockerContainerSummary:
    attrs = _attrs(container)
    state = _dict(attrs.get("State"))
    config = _dict(attrs.get("Config"))
    network_settings = _dict(attrs.get("NetworkSettings"))
    name = str(getattr(container, "name", "") or attrs.get("Name", "")).lstrip("/")
    image = str(
        getattr(getattr(container, "image", None), "short_id", "")
        or config.get("Image")
        or attrs.get("Image")
        or ""
    )
    raw_tags = getattr(getattr(container, "image", None), "tags", [])
    image_tags = [str(tag) for tag in raw_tags if tag is not None]
    return DockerContainerSummary(
        id=str(getattr(container, "id", "") or attrs.get("Id", ""))[:12],
        name=name,
        image=image,
        image_tags=image_tags,
        status=str(getattr(container, "status", "") or state.get("Status", "")),
        health=_health(state),
        labels={str(key): str(value) for key, value in _dict(config.get("Labels")).items()},
        ports=_ports(network_settings.get("Ports")),
        restart_count=int(state.get("RestartCount") or attrs.get("RestartCount") or 0),
    )


def _attrs(container: Any) -> dict[str, Any]:
    attrs = getattr(container, "attrs", {})
    return attrs if isinstance(attrs, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _health(state: dict[str, Any]) -> str | None:
    health = state.get("Health")
    if isinstance(health, dict):
        status = health.get("Status")
        return str(status) if status is not None else None
    return None


def _ports(value: Any) -> list[DockerContainerPort]:
    ports: list[DockerContainerPort] = []
    if not isinstance(value, dict):
        return ports
    for private, mappings in value.items():
        private_port, protocol = _split_port(str(private))
        for mapping in _iter_mappings(mappings):
            ports.append(
                DockerContainerPort(
                    private_port=private_port,
                    public_port=_int_or_none(mapping.get("HostPort")),
                    protocol=protocol,
                    ip=_str_or_none(mapping.get("HostIp")),
                )
            )
    return ports


def _iter_mappings(value: Any) -> Iterable[dict[str, Any]]:
    if value is None:
        return [{}]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _split_port(value: str) -> tuple[int | None, str | None]:
    port, _, protocol = value.partition("/")
    return _int_or_none(port), protocol or None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _reload(container: Any) -> None:
    reload_method = getattr(container, "reload", None)
    if callable(reload_method):
        reload_method()


_LOG_SUMMARY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("error", re.compile(r"\b(error|exception|failed|fatal)\b", re.IGNORECASE)),
    ("warning", re.compile(r"\b(warn|warning)\b", re.IGNORECASE)),
    ("restart", re.compile(r"\b(restart|restarting)\b", re.IGNORECASE)),
    ("permission", re.compile(r"\b(denied|permission|unauthorized)\b", re.IGNORECASE)),
]


def _summarize_logs(text: str) -> dict[str, Any]:
    counts = {name: 0 for name, _pattern in _LOG_SUMMARY_PATTERNS}
    samples: list[dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        for name, pattern in _LOG_SUMMARY_PATTERNS:
            if pattern.search(stripped):
                counts[name] += 1
                if len(samples) < 5:
                    samples.append({"category": name, "line": stripped[:300]})
                break
    return {
        "line_count": len(text.splitlines()),
        "pattern_counts": counts,
        "sample_findings": samples,
    }


def _docker_error_result(exc: Exception) -> ToolResult:
    if _is_permission_error(exc):
        return ToolResult(success=False, error=f"Docker socket proxy denied this request: {exc}")
    return ToolResult(success=False, error=f"Docker request failed: {exc}")


def _is_permission_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    response_code = getattr(response, "status_code", None)
    return status_code == 403 or response_code == 403 or "403" in str(exc)
