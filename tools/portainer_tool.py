from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from agent.settings import AppSettings, get_settings
from agent.tools.base import ToolResult, ToolSafety
from agent.tools.registry import ToolRegistry
from schemas.python.portainer import (
    PortainerListEndpointsArgs,
    PortainerListStacksArgs,
    PortainerRedeployStackArgs,
    PortainerStackDetailsArgs,
)


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="portainer_list_endpoints",
        description="List Portainer endpoints using API-token auth when configured.",
        args_model=PortainerListEndpointsArgs,
    )(list_endpoints)
    registry.register(
        name="portainer_list_stacks",
        description="List Portainer stacks, optionally scoped to an endpoint.",
        args_model=PortainerListStacksArgs,
    )(list_stacks)
    registry.register(
        name="portainer_stack_details",
        description="Read Portainer stack details.",
        args_model=PortainerStackDetailsArgs,
    )(stack_details)
    registry.register(
        name="portainer_redeploy_stack",
        description="Trigger a confirmed Portainer Git stack redeploy.",
        args_model=PortainerRedeployStackArgs,
        safety=ToolSafety.REQUIRES_CONFIRMATION,
    )(redeploy_stack)


def list_endpoints(arguments: BaseModel) -> ToolResult:
    PortainerListEndpointsArgs.model_validate(arguments)
    return _request_result("GET", "/api/endpoints")


def list_stacks(arguments: BaseModel) -> ToolResult:
    args = PortainerListStacksArgs.model_validate(arguments)
    params = {"endpointId": args.endpoint_id} if args.endpoint_id is not None else None
    return _request_result("GET", "/api/stacks", params=params)


def stack_details(arguments: BaseModel) -> ToolResult:
    args = PortainerStackDetailsArgs.model_validate(arguments)
    params = {"endpointId": args.endpoint_id} if args.endpoint_id is not None else None
    return _request_result("GET", f"/api/stacks/{args.stack_id}", params=params)


def redeploy_stack(arguments: BaseModel) -> ToolResult:
    args = PortainerRedeployStackArgs.model_validate(arguments)
    params = {"endpointId": args.endpoint_id}
    payload = {"pullImage": args.pull_image, "prune": args.prune}
    return _request_result(
        "POST",
        f"/api/stacks/{args.stack_id}/git/redeploy",
        params=params,
        json=payload,
    )


def _request_result(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> ToolResult:
    settings = get_settings()
    if not settings.portainer_configured:
        return ToolResult(success=False, error="Portainer integration is not configured.")
    try:
        with _client(settings) as client:
            response = client.request(method, path, params=params, json=json)
            if response.status_code == 403:
                return ToolResult(success=False, error="Portainer denied this request.")
            response.raise_for_status()
            return ToolResult(success=True, data=response.json())
    except httpx.HTTPError as exc:
        return ToolResult(success=False, error=f"Portainer request failed: {exc}")


def _client(settings: AppSettings) -> httpx.Client:
    headers = _auth_headers(settings)
    return httpx.Client(base_url=str(settings.portainer_base_url), headers=headers, timeout=10)


def _auth_headers(settings: AppSettings) -> dict[str, str]:
    if settings.portainer_api_token is not None:
        return {"X-API-Key": settings.portainer_api_token.get_secret_value()}
    jwt = _portainer_jwt(settings)
    return {"Authorization": f"Bearer {jwt}"}


def _portainer_jwt(settings: AppSettings) -> str:
    if settings.portainer_username is None or settings.portainer_password is None:
        raise httpx.HTTPError("Portainer JWT fallback requires username and password.")
    with httpx.Client(base_url=str(settings.portainer_base_url), timeout=10) as client:
        response = client.post(
            "/api/auth",
            json={
                "Username": settings.portainer_username,
                "Password": settings.portainer_password.get_secret_value(),
            },
        )
        response.raise_for_status()
        jwt = response.json().get("jwt")
        if not isinstance(jwt, str) or not jwt:
            raise httpx.HTTPError("Portainer auth response did not include a jwt.")
        return jwt
