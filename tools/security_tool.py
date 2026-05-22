from __future__ import annotations

import importlib
from typing import Any

from pydantic import BaseModel

from agent.settings import get_settings
from agent.tools.base import ToolResult
from agent.tools.registry import ToolRegistry
from schemas.python.security import SecurityPostureArgs


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="security_posture",
        description="Run read-only security checks for Docker and Proxmox risks.",
        args_model=SecurityPostureArgs,
    )(security_posture)


def security_posture(arguments: BaseModel) -> ToolResult:
    SecurityPostureArgs.model_validate(arguments)
    findings: list[dict[str, str]] = []
    
    settings = get_settings()

    _check_docker(settings, findings)
    _check_proxmox(settings, findings)
        
    return ToolResult(success=True, data={"findings": findings})


def _check_docker(settings: Any, findings: list[dict[str, str]]) -> None:
    try:
        docker = importlib.import_module("docker")
        client = docker.DockerClient(base_url=settings.docker_socket_proxy_url)
        for container in client.containers.list(all=True):
            name = getattr(container, "name", "unknown")
            attrs = getattr(container, "attrs", {})
            host_config = attrs.get("HostConfig", {})
            
            if host_config.get("Privileged"):
                findings.append({
                    "severity": "high",
                    "type": "privileged_container",
                    "evidence": f"Container '{name}' is running in privileged mode.",
                    "remediation": "Remove --privileged and use specific capabilities instead."
                })
            
            if host_config.get("NetworkMode") == "host":
                findings.append({
                    "severity": "medium",
                    "type": "host_networking",
                    "evidence": f"Container '{name}' uses host networking.",
                    "remediation": "Use bridge networks and publish only necessary ports."
                })
                
            policy = host_config.get("RestartPolicy", {}).get("Name")
            if not policy or policy == "no":
                findings.append({
                    "severity": "low",
                    "type": "missing_restart_policy",
                    "evidence": f"Container '{name}' has no restart policy.",
                    "remediation": "Set restart policy to unless-stopped or always."
                })
                
    except Exception as exc:
        findings.append({
            "severity": "warning",
            "type": "docker_check_failed",
            "evidence": f"Could not check Docker security: {exc}",
            "remediation": "Ensure Docker socket proxy is reachable."
        })


def _check_proxmox(settings: Any, findings: list[dict[str, str]]) -> None:
    if not settings.proxmox.configured:
        return
    try:
        from tools.proxmox_tool import build_proxmox_client, _split_token_id
        client = build_proxmox_client(settings)
        token_id = settings.proxmox_token_id.get_secret_value() if settings.proxmox_token_id else ""
        if not token_id:
            return
            
        perms = client.access.permissions.get(userid=token_id)
        all_privs: set[str] = set()
        
        # permissions can be a dict mapping path to privileges
        if isinstance(perms, dict):
            for path, data in perms.items():
                if isinstance(data, dict) and "privs" in data:
                    all_privs.update(data["privs"])
                elif isinstance(data, list):
                    all_privs.update(data)
                    
        dangerous = {"VM.Allocate", "Sys.Modify", "Datastore.Allocate", "User.Modify"}
        found_dangerous = dangerous.intersection(all_privs)
        if found_dangerous:
            findings.append({
                "severity": "high",
                "type": "proxmox_privilege_drift",
                "evidence": f"Proxmox token has dangerous privileges: {', '.join(sorted(found_dangerous))}",
                "remediation": "Restrict token to audit-only roles."
            })
    except Exception as exc:
         findings.append({
            "severity": "warning",
            "type": "proxmox_check_failed",
            "evidence": f"Could not check Proxmox security: {exc}",
            "remediation": "Ensure Proxmox API token is valid."
        })
