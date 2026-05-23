from __future__ import annotations

import ipaddress
import subprocess
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from pydantic import BaseModel

from agent.mock_mode import MockMode
from agent.settings import AppSettings, get_settings
from agent.tools.base import ToolResult
from agent.tools.registry import ToolRegistry
from schemas.python.network import (
    NetworkScanArgs,
    PiholeQueriesArgs,
    PiholeRecentBlockedArgs,
    PiholeSummaryArgs,
    UnboundStatsArgs,
    UnknownDeviceArgs,
)

_RFC1918_BLOCKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="pihole_summary",
        description="Read Pi-hole v5 summary stats (total queries, ads blocked, percent blocked).",
        args_model=PiholeSummaryArgs,
    )(pihole_summary)
    registry.register(
        name="pihole_recent_blocked",
        description="Read the most recent Pi-hole blocked domain.",
        args_model=PiholeRecentBlockedArgs,
    )(pihole_recent_blocked)
    registry.register(
        name="pihole_recent_queries",
        description="Read a bounded number of recent Pi-hole DNS queries.",
        args_model=PiholeQueriesArgs,
    )(pihole_recent_queries)
    registry.register(
        name="unbound_stats",
        description="Read Unbound resolver stats via unbound-control and parse key/value metrics.",
        args_model=UnboundStatsArgs,
    )(unbound_stats)
    registry.register(
        name="network_scan",
        description=(
            "Run an nmap host discovery on a configured RFC1918 subnet. Refuses public IP "
            "ranges and any subnet not in network_allowed_subnets."
        ),
        args_model=NetworkScanArgs,
    )(network_scan)
    registry.register(
        name="network_unknown_devices",
        description=(
            "Scan a configured RFC1918 subnet and flag devices whose MAC is not in the "
            "network_known_macs allowlist."
        ),
        args_model=UnknownDeviceArgs,
    )(network_unknown_devices)


def pihole_summary(arguments: BaseModel) -> ToolResult:
    args = PiholeSummaryArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("pihole_summary", args)
    if mock_result is not None:
        return mock_result
    return _pihole_get({"summary": ""})


def pihole_recent_blocked(arguments: BaseModel) -> ToolResult:
    args = PiholeRecentBlockedArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("pihole_recent_blocked", args)
    if mock_result is not None:
        return mock_result
    return _pihole_get({"recentBlocked": ""}, expect_json=False)


def pihole_recent_queries(arguments: BaseModel) -> ToolResult:
    args = PiholeQueriesArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("pihole_recent_queries", args)
    if mock_result is not None:
        return mock_result
    return _pihole_get({"getAllQueries": args.limit})


def unbound_stats(arguments: BaseModel) -> ToolResult:
    args = UnboundStatsArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("unbound_stats", args)
    if mock_result is not None:
        return mock_result
    settings = get_settings()
    try:
        output = run_unbound_control(settings)
    except FileNotFoundError:
        return ToolResult(success=False, error="unbound-control is not installed on this host.")
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        return ToolResult(success=False, error=f"unbound-control failed: {stderr or exc}")
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, error="unbound-control timed out.")
    return ToolResult(success=True, data=parse_unbound_stats(output))


def network_scan(arguments: BaseModel) -> ToolResult:
    args = NetworkScanArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("network_scan", args)
    if mock_result is not None:
        return mock_result
    settings = get_settings()
    refusal = _refuse_unsafe_subnet(args.subnet, settings)
    if refusal is not None:
        return refusal
    try:
        xml = run_nmap(args.subnet, detect_services=args.detect_services)
    except FileNotFoundError:
        return ToolResult(success=False, error="nmap is not installed on this host.")
    except subprocess.CalledProcessError as exc:
        return ToolResult(success=False, error=f"nmap failed: {(exc.stderr or '').strip() or exc}")
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, error="nmap timed out.")
    hosts = parse_nmap_xml(xml)
    return ToolResult(
        success=True,
        data={"subnet": args.subnet, "host_count": len(hosts), "hosts": hosts},
    )


def network_unknown_devices(arguments: BaseModel) -> ToolResult:
    args = UnknownDeviceArgs.model_validate(arguments)
    mock_result = MockMode.tool_result("network_unknown_devices", args, required=False)
    if mock_result is not None:
        return mock_result
    settings = get_settings()
    refusal = _refuse_unsafe_subnet(args.subnet, settings)
    if refusal is not None:
        return refusal
    scan = network_scan(NetworkScanArgs(subnet=args.subnet, detect_services=False))
    if not scan.success or not isinstance(scan.data, dict):
        return scan
    known = {mac.lower() for mac in settings.network_known_macs}
    unknown = [
        host
        for host in scan.data.get("hosts", [])
        if host.get("mac") and host["mac"].lower() not in known
    ]
    return ToolResult(
        success=True,
        data={
            "subnet": args.subnet,
            "known_count": len(known),
            "unknown_count": len(unknown),
            "unknown_devices": unknown,
        },
    )


def _pihole_get(params: dict[str, Any], *, expect_json: bool = True) -> ToolResult:
    settings = get_settings()
    if not settings.pihole.configured:
        return ToolResult(success=False, error="Pi-hole integration is not configured.")
    token = settings.pihole_api_token.get_secret_value() if settings.pihole_api_token else ""
    merged: dict[str, Any] = {**params, "auth": token}
    try:
        with _pihole_client(settings) as client:
            response = client.get("/admin/api.php", params=merged)
            response.raise_for_status()
            if not expect_json:
                return ToolResult(success=True, data={"raw": response.text})
            payload = response.json()
    except httpx.HTTPError as exc:
        return ToolResult(success=False, error=f"Pi-hole request failed: {exc}")
    if isinstance(payload, list) and not payload:
        return ToolResult(
            success=False,
            error="Pi-hole returned an empty list, which usually means auth failed.",
        )
    return ToolResult(success=True, data=payload)


def _pihole_client(settings: AppSettings) -> httpx.Client:
    return httpx.Client(base_url=str(settings.pihole_base_url), timeout=10)


def run_unbound_control(settings: AppSettings) -> str:
    cmd = ["unbound-control"]
    if settings.unbound_host:
        cmd.extend(["-s", f"{settings.unbound_host}@{settings.unbound_port}"])
    cmd.append("stats_noreset")
    result = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, timeout=10, check=True
    )
    return result.stdout


def parse_unbound_stats(output: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for line in output.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        metrics[key] = _coerce_metric(value)
    return metrics


def _coerce_metric(value: str) -> Any:
    if not value:
        return value
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def run_nmap(subnet: str, *, detect_services: bool) -> str:
    cmd = ["nmap", "-oX", "-"]
    if detect_services:
        cmd.extend(["-sV", "--top-ports", "20"])
    else:
        cmd.append("-sn")
    cmd.append(subnet)
    result = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, timeout=120, check=True
    )
    return result.stdout


def parse_nmap_xml(xml_text: str) -> list[dict[str, Any]]:
    if not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)  # noqa: S314 - nmap output is trusted local input
    except ET.ParseError:
        return []
    hosts: list[dict[str, Any]] = []
    for host in root.findall("host"):
        state_el = host.find("status")
        state = state_el.get("state") if state_el is not None else None
        ip: str | None = None
        mac: str | None = None
        vendor: str | None = None
        for addr in host.findall("address"):
            addr_type = addr.get("addrtype")
            if addr_type == "ipv4" and ip is None:
                ip = addr.get("addr")
            elif addr_type == "mac":
                mac = addr.get("addr")
                vendor = addr.get("vendor")
        hostname_el = host.find("hostnames/hostname")
        hostname = hostname_el.get("name") if hostname_el is not None else None
        services = [_service_row(port) for port in host.findall("ports/port")]
        hosts.append(
            {
                "ip": ip,
                "hostname": hostname,
                "mac": mac,
                "vendor": vendor,
                "state": state,
                "services": [row for row in services if row],
            }
        )
    return hosts


def _service_row(port_el: ET.Element) -> dict[str, Any] | None:
    state_el = port_el.find("state")
    if state_el is not None and state_el.get("state") != "open":
        return None
    service_el = port_el.find("service")
    return {
        "port": _to_int(port_el.get("portid")),
        "protocol": port_el.get("protocol"),
        "service": service_el.get("name") if service_el is not None else None,
        "product": service_el.get("product") if service_el is not None else None,
    }


def _to_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _refuse_unsafe_subnet(subnet: str, settings: AppSettings) -> ToolResult | None:
    try:
        network = ipaddress.ip_network(subnet, strict=False)
    except ValueError as exc:
        return ToolResult(success=False, error=f"Invalid subnet: {exc}")
    if not any(network.subnet_of(block) for block in _RFC1918_BLOCKS):  # type: ignore[arg-type]
        return ToolResult(
            success=False,
            error=f"Refusing to scan {subnet}: only RFC1918 private ranges are allowed.",
        )
    if not settings.network_allowed_subnets:
        return ToolResult(
            success=False,
            error="No allowed subnets configured. Set FOXHOLE_NETWORK_ALLOWED_SUBNETS first.",
        )
    allowed = [
        ipaddress.ip_network(value, strict=False) for value in settings.network_allowed_subnets
    ]
    if not any(network.subnet_of(block) for block in allowed):  # type: ignore[arg-type]
        return ToolResult(
            success=False,
            error=(f"Refusing to scan {subnet}: not within configured network_allowed_subnets."),
        )
    return None
