from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from agent.mock_mode import MockMode
from agent.settings import get_settings
from agent.tools.base import ToolResult
from agent.tools.registry import ToolRegistry
from schemas.python.caddy import CaddyListRoutesArgs, CaddyRouteDiagnosisArgs


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="caddy_list_routes",
        description=(
            "Read Caddy routes and reverse-proxy upstream targets from Caddyfile or admin API."
        ),
        args_model=CaddyListRoutesArgs,
    )(list_routes)
    registry.register(
        name="caddy_route_diagnosis",
        description=(
            "Flag Caddy reverse-proxy upstreams that look missing or likely to produce 502s."
        ),
        args_model=CaddyRouteDiagnosisArgs,
    )(route_diagnosis)


def list_routes(arguments: BaseModel) -> ToolResult:
    args = CaddyListRoutesArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("caddy_list_routes", args)
    if mock_result is not None:
        return mock_result
    settings = get_settings()
    if not settings.caddy_configured:
        return ToolResult(success=False, error="Caddy integration is not configured.")

    routes: list[dict[str, Any]] = []
    sources: list[str] = []
    if args.include_admin_config and settings.caddy_admin_api_url:
        admin_result = _admin_config_routes(str(settings.caddy_admin_api_url))
        if not admin_result.success:
            return admin_result
        routes.extend(_list_of_dicts(_dict(admin_result.data).get("routes")))
        sources.append("admin_api")
    elif settings.caddy_config_path:
        path = Path(settings.caddy_config_path)
        try:
            text = path.read_text()
        except OSError as exc:
            return ToolResult(success=False, error=f"Could not read Caddy config: {exc}")
        routes.extend(parse_caddyfile_routes(text))
        sources.append(str(path))

    return ToolResult(
        success=True,
        data={"route_count": len(routes), "sources": sources, "routes": routes},
    )


def route_diagnosis(arguments: BaseModel) -> ToolResult:
    args = CaddyRouteDiagnosisArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("caddy_route_diagnosis", args, required=False)
    if mock_result is not None:
        return mock_result
    routes_result = list_routes(CaddyListRoutesArgs())
    if not routes_result.success:
        return routes_result
    known = {name.lower() for name in args.known_container_names}
    findings: list[dict[str, Any]] = []
    for route in _list_of_dicts(_dict(routes_result.data).get("routes")):
        for upstream in route.get("upstreams", []) or []:
            target = str(upstream)
            host, port = _split_host_port(target)
            if not host:
                continue
            if port is None:
                findings.append(_finding("missing_upstream_port", route, target, "No port found."))
            if _looks_like_container(host) and known and host.lower() not in known:
                findings.append(
                    _finding(
                        "missing_container_upstream",
                        route,
                        target,
                        "Upstream host is not in the known Docker container list.",
                    )
                )
            if host in {"0.0.0.0", "::"}:
                findings.append(
                    _finding(
                        "wildcard_upstream",
                        route,
                        target,
                        "Wildcard bind address is not a useful reverse-proxy upstream.",
                    )
                )
    return ToolResult(
        success=True,
        data={
            "route_count": _dict(routes_result.data).get("route_count"),
            "finding_count": len(findings),
            "findings": findings,
        },
    )


def parse_caddyfile_routes(text: str) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    current_site = "global"
    stack: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.endswith("{"):
            header = line[:-1].strip()
            stack.append(header)
            if header and not header.startswith(("handle", "route", "@", "tls", "header")):
                current_site = header
            continue
        if line == "}":
            if stack:
                stack.pop()
            current_site = stack[0] if stack else "global"
            continue
        if line.startswith("reverse_proxy"):
            parts = line.split()
            upstreams = [part for part in parts[1:] if not part.startswith("{")]
            routes.append(
                {
                    "source": "caddyfile",
                    "route": current_site,
                    "match": _current_match(stack),
                    "upstreams": upstreams,
                }
            )
    return routes


def _admin_config_routes(base_url: str) -> ToolResult:
    try:
        with httpx.Client(base_url=base_url, timeout=5) as client:
            response = client.get("/config/")
            response.raise_for_status()
            config = response.json()
    except httpx.HTTPError as exc:
        return ToolResult(success=False, error=f"Caddy admin API request failed: {exc}")
    routes = _routes_from_json(config)
    return ToolResult(success=True, data={"routes": routes})


def _routes_from_json(value: Any) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("handler") == "reverse_proxy":
            upstreams = [
                str(upstream.get("dial"))
                for upstream in value.get("upstreams", [])
                if isinstance(upstream, dict) and upstream.get("dial")
            ]
            routes.append(
                {
                    "source": "admin_api",
                    "route": str(value.get("@id") or "reverse_proxy"),
                    "match": None,
                    "upstreams": upstreams,
                }
            )
        for child in value.values():
            routes.extend(_routes_from_json(child))
    elif isinstance(value, list):
        for child in value:
            routes.extend(_routes_from_json(child))
    return routes


def _finding(kind: str, route: dict[str, Any], upstream: str, detail: str) -> dict[str, Any]:
    return {
        "severity": "warning",
        "type": kind,
        "route": route.get("route"),
        "match": route.get("match"),
        "upstream": upstream,
        "detail": detail,
        "next_action": "Check Caddy route target, Docker service name, and upstream port.",
    }


def _current_match(stack: list[str]) -> str | None:
    for item in reversed(stack):
        if item.startswith("handle ") or item.startswith("route "):
            return item
    return None


def _split_host_port(target: str) -> tuple[str | None, int | None]:
    cleaned = re.sub(r"^https?://", "", target).split("/", 1)[0]
    if ":" not in cleaned:
        return cleaned or None, None
    host, port_text = cleaned.rsplit(":", 1)
    try:
        return host.strip("[]") or None, int(port_text)
    except ValueError:
        return host.strip("[]") or None, None


def _looks_like_container(host: str) -> bool:
    if host in {"localhost", "127.0.0.1"}:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return True


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
