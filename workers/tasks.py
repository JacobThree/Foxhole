from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from agent.db.repositories import prune_durable_history
from agent.events import store_check_result
from agent.mock_mode import MockMode
from agent.settings import AppSettings, get_settings
from schemas.python.arr import ArrHealthArgs, ArrImportDiagnosisArgs, ArrQueueArgs, ArrService
from schemas.python.backups import BackupStorageHealthArgs
from schemas.python.chat import (
    ConfidenceLevel,
    DiagnosticFinding,
    EvidenceItem,
    RiskLevel,
    SuggestedAction,
)
from schemas.python.docker import DockerListContainersArgs, DockerRestartLoopArgs
from schemas.python.events import CheckStatus, ScheduledCheckResult
from schemas.python.network import PiholeSummaryArgs, UnboundStatsArgs, UnknownDeviceArgs
from schemas.python.plex import (
    PlexBufferingDiagnosisArgs,
    PlexLogAnalysisArgs,
)
from schemas.python.security import SecurityPostureArgs
from schemas.python.uptime_kuma import UptimeKumaMonitorStatusArgs, UptimeKumaRecentFailuresArgs
from tools import (
    arr_tool,
    backup_tool,
    docker_tool,
    network_tool,
    plex_tool,
    security_tool,
    uptime_kuma_tool,
)
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduledCheckDefinition:
    name: str
    source: str
    check_fn: CallableCheck
    interval_seconds: int


def scheduled_check_definitions() -> tuple[ScheduledCheckDefinition, ...]:
    return SCHEDULED_CHECKS


def run_scheduled_check(check_name: str) -> ScheduledCheckResult:
    definition = _scheduled_check_by_name(check_name)
    return _run_check(definition.name, definition.source, definition.check_fn)


@celery_app.task(name="tasks.check_container_health")  # type: ignore[untyped-decorator]
def check_container_health() -> dict[str, Any]:
    logger.info("Checking container health")
    return run_scheduled_check("container_health").model_dump(mode="json")


@celery_app.task(name="tasks.check_storage_thresholds")  # type: ignore[untyped-decorator]
def check_storage_thresholds() -> dict[str, Any]:
    logger.info("Checking storage thresholds")
    return run_scheduled_check("storage_thresholds").model_dump(mode="json")


@celery_app.task(name="tasks.check_arr_imports")  # type: ignore[untyped-decorator]
def check_arr_imports() -> dict[str, Any]:
    logger.info("Checking *Arr imports")
    return run_scheduled_check("arr_imports").model_dump(mode="json")


@celery_app.task(name="tasks.check_plex_db_health")  # type: ignore[untyped-decorator]
def check_plex_db_health() -> dict[str, Any]:
    logger.info("Checking Plex DB health")
    return run_scheduled_check("plex_db_health").model_dump(mode="json")


@celery_app.task(name="tasks.scan_rogue_macs")  # type: ignore[untyped-decorator]
def scan_rogue_macs() -> dict[str, Any]:
    logger.info("Scanning for rogue MACs")
    return run_scheduled_check("rogue_macs").model_dump(mode="json")


@celery_app.task(name="tasks.check_uptime_kuma_monitors")  # type: ignore[untyped-decorator]
def check_uptime_kuma_monitors() -> dict[str, Any]:
    logger.info("Checking Uptime Kuma monitors")
    return run_scheduled_check("uptime_kuma_monitors").model_dump(mode="json")


@celery_app.task(name="foxhole.retention_prune")  # type: ignore[untyped-decorator]
def retention_prune() -> dict[str, int]:
    logger.info("Pruning durable history by configured retention policy")
    return prune_durable_history(get_settings())


def _scheduled_check_by_name(check_name: str) -> ScheduledCheckDefinition:
    for definition in SCHEDULED_CHECKS:
        if definition.name == check_name:
            return definition
    raise ValueError(f"Unknown scheduled check: {check_name}")


def _run_check(
    check: str,
    source: str,
    check_fn: CallableCheck,
) -> ScheduledCheckResult:
    started = time.perf_counter()
    try:
        result = check_fn(get_settings())
    except Exception as exc:  # pragma: no cover - defensive Celery boundary
        logger.exception("Scheduled check failed: %s", check)
        result = ScheduledCheckResult(
            check=check,
            source=source,
            status=CheckStatus.FAILED,
            severity="critical",
            summary=f"{check} failed before producing diagnostics.",
            evidence=[EvidenceItem(source=source, summary=str(exc))],
        )
    result.duration_ms = round((time.perf_counter() - started) * 1000, 2)
    _emit_check_result(result)
    return result


def _check_container_health(settings: AppSettings) -> ScheduledCheckResult:
    if not settings.docker.configured and not settings.mock_mode:
        return _skipped(
            "container_health",
            "docker",
            "Docker integration is disabled or missing socket proxy configuration.",
        )

    containers_result = docker_tool.list_containers(DockerListContainersArgs(all=True))
    if not containers_result.success:
        return _failed_tool_result(
            "container_health",
            "docker",
            "Docker container inventory is unavailable.",
            containers_result.error,
        )

    containers = _list_of_dicts(containers_result.data)
    findings: list[DiagnosticFinding] = []
    for container in containers:
        name = str(container.get("name") or container.get("id") or "unknown")
        health = str(container.get("health") or "").lower()
        status = str(container.get("status") or "").lower()
        if health and health not in {"healthy", "none"}:
            findings.append(
                _finding(
                    "Unhealthy Docker container",
                    f"{name} reports health={health}.",
                    RiskLevel.MEDIUM,
                    "docker_list_containers",
                    {"container": name, "health": health, "status": status},
                    "Inspect the container healthcheck and recent logs.",
                )
            )
        if status in {"restarting", "dead"}:
            findings.append(
                _finding(
                    "Docker container is not stable",
                    f"{name} is {status}.",
                    RiskLevel.HIGH,
                    "docker_list_containers",
                    {"container": name, "status": status},
                    "Inspect logs and restart policy before restarting the container.",
                    requires_confirmation=True,
                )
            )

    loop_result = docker_tool.detect_restart_loops(DockerRestartLoopArgs(all=True, min_restarts=3))
    if loop_result.success:
        for candidate in _list_of_dicts(_dict(loop_result.data).get("restart_loop_candidates")):
            name = str(candidate.get("name") or candidate.get("id") or "unknown")
            findings.append(
                _finding(
                    "Docker restart loop candidate",
                    f"{name} has restarted {candidate.get('restart_count', 0)} time(s).",
                    RiskLevel.HIGH,
                    "docker_detect_restart_loops",
                    {
                        "container": name,
                        "restart_count": candidate.get("restart_count"),
                        "status": candidate.get("status"),
                    },
                    "Inspect logs and confirm a restart/remediation before acting.",
                    requires_confirmation=True,
                )
            )
    else:
        findings.append(
            _finding(
                "Docker restart-loop check failed",
                loop_result.error or "Restart-loop check did not return data.",
                RiskLevel.MEDIUM,
                "docker_detect_restart_loops",
                {"error": loop_result.error},
                "Verify the Docker socket proxy allows read-only container listing.",
            )
        )

    security_result = security_tool.security_posture(SecurityPostureArgs())
    if security_result.success:
        for row in _list_of_dicts(_dict(security_result.data).get("findings")):
            finding_type = str(row.get("type") or "")
            if finding_type not in {
                "privileged_container",
                "host_networking",
                "missing_restart_policy",
                "docker_check_failed",
            }:
                continue
            findings.append(
                _finding(
                    _title_from_type(finding_type),
                    str(row.get("evidence") or finding_type),
                    _risk_from_tool_severity(row.get("severity")),
                    "security_posture",
                    row,
                    str(row.get("remediation") or "Review the Docker security finding."),
                )
            )
    else:
        findings.append(
            _finding(
                "Docker security check failed",
                security_result.error or "Security posture check did not return data.",
                RiskLevel.MEDIUM,
                "security_posture",
                {"error": security_result.error},
                "Verify Docker read-only inspection is available.",
            )
        )

    evidence = [
        EvidenceItem(
            source="docker_list_containers",
            summary=f"Checked {len(containers)} Docker container(s).",
            data={
                "container_count": len(containers),
                "restart_loop_check": loop_result.success,
                "security_check": security_result.success,
            },
        )
    ]
    return _result_from_findings(
        check="container_health",
        source="docker",
        ok_summary="Docker container health checks passed.",
        issue_summary=f"{len(findings)} Docker container issue(s) found.",
        evidence=evidence,
        findings=findings,
    )


def _check_storage_thresholds(settings: AppSettings) -> ScheduledCheckResult:
    if not settings.proxmox.configured and not settings.mock_mode:
        return _skipped(
            "storage_thresholds",
            "storage",
            "Proxmox integration is disabled or missing API token configuration.",
        )

    result = backup_tool.backup_storage_health(BackupStorageHealthArgs())
    if not result.success:
        return _failed_tool_result(
            "storage_thresholds",
            "storage",
            "Storage and backup data is unavailable.",
            result.error,
        )

    data = _dict(result.data)
    tool_findings = _list_of_dicts(data.get("findings"))
    findings = [
        _finding(
            _title_from_type(str(row.get("type") or "storage_finding")),
            _storage_summary(row),
            _risk_from_tool_severity(row.get("severity")),
            "backup_storage_health",
            row,
            str(row.get("next_action") or "Review the storage or backup finding."),
        )
        for row in tool_findings
    ]
    evidence = [
        EvidenceItem(
            source="backup_storage_health",
            summary="Checked Proxmox storage usage and backup job freshness.",
            data={
                "storage_count": len(_list_of_dicts(data.get("storage"))),
                "backup_job_count": len(_list_of_dicts(data.get("backup_jobs"))),
                "local_filesystem_count": len(_list_of_dicts(data.get("local_filesystems"))),
            },
        )
    ]
    return _result_from_findings(
        check="storage_thresholds",
        source="storage",
        ok_summary="Storage and backup checks passed.",
        issue_summary=f"{len(findings)} storage or backup issue(s) found.",
        evidence=evidence,
        findings=findings,
    )


def _check_arr_imports(settings: AppSettings) -> ScheduledCheckResult:
    services = _configured_arr_services(settings)
    if not services:
        return _skipped(
            "arr_imports",
            "arr",
            "Sonarr and Radarr integrations are disabled or missing API configuration.",
        )

    findings: list[DiagnosticFinding] = []
    checked: list[str] = []
    for service in services:
        checked.append(service.value)
        queue_result = arr_tool.queue(ArrQueueArgs(service=service, page_size=100))
        if queue_result.success:
            findings.extend(_arr_queue_findings(service, _queue_records(queue_result.data)))
        else:
            findings.append(
                _finding(
                    f"{service.value.title()} queue unavailable",
                    queue_result.error or "Queue request failed.",
                    RiskLevel.MEDIUM,
                    "arr_queue",
                    {"service": service.value, "error": queue_result.error},
                    "Verify the API URL and key before investigating imports.",
                )
            )

        health_result = arr_tool.health(ArrHealthArgs(service=service))
        if health_result.success:
            findings.extend(_arr_health_findings(service, _list_of_dicts(health_result.data)))
        else:
            findings.append(
                _finding(
                    f"{service.value.title()} health unavailable",
                    health_result.error or "Health request failed.",
                    RiskLevel.MEDIUM,
                    "arr_health",
                    {"service": service.value, "error": health_result.error},
                    "Verify the API URL and key before investigating health warnings.",
                )
            )

        import_result = arr_tool.import_diagnosis(
            ArrImportDiagnosisArgs(service=service, page_size=100)
        )
        if import_result.success:
            findings.extend(_arr_import_findings(service, _dict(import_result.data)))
        else:
            findings.append(
                _finding(
                    f"{service.value.title()} import diagnosis unavailable",
                    import_result.error or "Import diagnosis failed.",
                    RiskLevel.MEDIUM,
                    "arr_import_diagnosis",
                    {"service": service.value, "error": import_result.error},
                    "Verify queue and root-folder API access.",
                )
            )

    evidence = [
        EvidenceItem(
            source="arr_imports",
            summary=f"Checked {', '.join(checked)} queue, health, and root-folder state.",
            data={"services": checked},
        )
    ]
    return _result_from_findings(
        check="arr_imports",
        source="arr",
        ok_summary="Sonarr/Radarr import checks passed.",
        issue_summary=f"{len(findings)} Sonarr/Radarr import issue(s) found.",
        evidence=evidence,
        findings=findings,
    )


def _check_plex_db_health(settings: AppSettings) -> ScheduledCheckResult:
    if not settings.plex.configured and not settings.mock_mode:
        return _skipped(
            "plex_db_health",
            "plex",
            "Plex integration is disabled or missing URL/token configuration.",
        )

    findings: list[DiagnosticFinding] = []
    evidence = []

    buffering_result = plex_tool.buffering_diagnosis(PlexBufferingDiagnosisArgs())
    if buffering_result.success:
        data = _dict(buffering_result.data)
        risk = str(data.get("risk") or "low")
        evidence.append(
            EvidenceItem(
                source="plex_buffering_diagnosis",
                summary=f"Plex buffering risk is {risk}.",
                data={
                    "risk": risk,
                    "session_count": data.get("session_count"),
                    "software_transcode_count": data.get("software_transcode_count"),
                    "risk_factors": data.get("risk_factors", []),
                },
            )
        )
        if risk in {"elevated", "high"}:
            findings.append(
                _finding(
                    "Plex buffering risk",
                    f"Plex reports {risk} buffering risk.",
                    RiskLevel.HIGH if risk == "high" else RiskLevel.MEDIUM,
                    "plex_buffering_diagnosis",
                    data,
                    "Review active sessions, codec support, and host CPU/GPU utilization.",
                )
            )
    else:
        findings.append(
            _finding(
                "Plex buffering diagnosis unavailable",
                buffering_result.error or "Plex buffering diagnosis failed.",
                RiskLevel.MEDIUM,
                "plex_buffering_diagnosis",
                {"error": buffering_result.error},
                "Verify Plex API connectivity.",
            )
        )

    plex_log_path = settings.plex_log_path
    if not plex_log_path and settings.mock_mode:
        plex_log_path = MockMode.default_plex_log_path()
    if plex_log_path:
        log_result = plex_tool.analyze_logs(PlexLogAnalysisArgs(log_path=plex_log_path))
        if log_result.success:
            data = _dict(log_result.data)
            evidence.append(
                EvidenceItem(
                    source="plex_analyze_logs",
                    summary="Checked Plex log tail for database and transcode warnings.",
                    data={
                        "log_path": data.get("log_path"),
                        "bytes_read": data.get("bytes_read"),
                        "finding_counts": data.get("finding_counts", {}),
                    },
                )
            )
            findings.extend(_plex_log_findings(data))
        else:
            findings.append(
                _finding(
                    "Plex log health unavailable",
                    log_result.error or "Plex log analysis failed.",
                    RiskLevel.MEDIUM,
                    "plex_analyze_logs",
                    {"log_path": settings.plex_log_path, "error": log_result.error},
                    "Mount the Plex log path read-only or update FOXHOLE_PLEX_LOG_PATH.",
                )
            )
    else:
        evidence.append(
            EvidenceItem(
                source="plex_analyze_logs",
                summary=(
                    "Plex log path is not configured; DB lock and transcode log checks skipped."
                ),
            )
        )

    return _result_from_findings(
        check="plex_db_health",
        source="plex",
        ok_summary="Plex buffering and log checks passed.",
        issue_summary=f"{len(findings)} Plex issue(s) found.",
        evidence=evidence,
        findings=findings,
    )


def _scan_rogue_macs(settings: AppSettings) -> ScheduledCheckResult:
    subnets = settings.network_allowed_subnets or (
        MockMode.default_subnets() if settings.mock_mode else []
    )
    if not subnets:
        return _skipped(
            "rogue_macs",
            "network",
            "No allowed subnets configured; refusing to run network discovery.",
        )

    findings: list[DiagnosticFinding] = []
    scanned_subnets: list[str] = []
    for subnet in subnets:
        result = network_tool.network_unknown_devices(UnknownDeviceArgs(subnet=subnet))
        if result.success:
            data = _dict(result.data)
            scanned_subnets.append(subnet)
            for device in _list_of_dicts(data.get("unknown_devices")):
                address = device.get("ip") or "unknown address"
                vendor = device.get("vendor") or "unknown vendor"
                findings.append(
                    _finding(
                        "Unknown MAC detected",
                        f"{address} has MAC {device.get('mac')} ({vendor}).",
                        RiskLevel.MEDIUM,
                        "network_unknown_devices",
                        {
                            "subnet": subnet,
                            "ip": device.get("ip"),
                            "mac": device.get("mac"),
                            "vendor": device.get("vendor"),
                            "hostname": device.get("hostname"),
                        },
                        "Identify the device before adding it to network_known_macs.",
                    )
                )
        else:
            findings.append(
                _finding(
                    "Network discovery refused or failed",
                    result.error or f"Could not scan {subnet}.",
                    RiskLevel.MEDIUM,
                    "network_unknown_devices",
                    {"subnet": subnet, "error": result.error},
                    "Keep scans limited to configured RFC1918 subnets.",
                )
            )

    dns_evidence, dns_findings = _dns_diagnostics(settings)
    findings.extend(dns_findings)
    evidence = [
        EvidenceItem(
            source="network_unknown_devices",
            summary=f"Checked {len(scanned_subnets)} configured subnet(s).",
            data={
                "configured_subnets": settings.network_allowed_subnets,
                "mock_subnets": subnets if settings.mock_mode else [],
                "scanned_subnets": scanned_subnets,
                "known_mac_count": len(settings.network_known_macs),
            },
        )
    ]
    evidence.extend(dns_evidence)
    return _result_from_findings(
        check="rogue_macs",
        source="network",
        ok_summary="Network discovery and DNS checks passed.",
        issue_summary=f"{len(findings)} network or DNS issue(s) found.",
        evidence=evidence,
        findings=findings,
    )


def _check_uptime_kuma_monitors(settings: AppSettings) -> ScheduledCheckResult:
    if not settings.uptime_kuma.configured and not settings.mock_mode:
        return _skipped(
            "uptime_kuma_monitors",
            "uptime_kuma",
            "Uptime Kuma integration is disabled or missing URL/token configuration.",
        )

    status_result = uptime_kuma_tool.monitor_status(UptimeKumaMonitorStatusArgs())
    if not status_result.success:
        return _failed_tool_result(
            "uptime_kuma_monitors",
            "uptime_kuma",
            "Uptime Kuma monitor status is unavailable.",
            status_result.error,
        )

    status_data = _dict(status_result.data)
    monitors = _list_of_dicts(status_data.get("monitors"))
    findings: list[DiagnosticFinding] = []
    for monitor in monitors:
        status = str(monitor.get("status") or "unknown").lower()
        if status in {"up", "unknown"}:
            continue
        risk = RiskLevel.HIGH if status == "down" else RiskLevel.MEDIUM
        findings.append(
            _finding(
                "Uptime Kuma monitor failing",
                f"{monitor.get('name') or 'Monitor'} is {status}.",
                risk,
                "uptime_kuma_monitor_status",
                monitor,
                "Correlate the failed monitor with Docker, DNS, and reverse-proxy diagnostics.",
            )
        )

    failures_result = uptime_kuma_tool.recent_failures(UptimeKumaRecentFailuresArgs(limit=10))
    if failures_result.success:
        for failure in _list_of_dicts(_dict(failures_result.data).get("failures")):
            findings.append(
                _finding(
                    "Uptime Kuma recent failure",
                    str(failure.get("message") or failure.get("monitor_name") or "Monitor failure"),
                    _risk_from_tool_severity(failure.get("status")),
                    "uptime_kuma_recent_failures",
                    failure,
                    "Use the failure timestamp to correlate against recent Foxhole events.",
                )
            )

    evidence = [
        EvidenceItem(
            source="uptime_kuma_monitor_status",
            summary=f"Checked {len(monitors)} Uptime Kuma monitor(s).",
            data={
                "monitor_count": len(monitors),
                "down_count": status_data.get("down_count"),
                "degraded_count": status_data.get("degraded_count"),
            },
        )
    ]
    return _result_from_findings(
        check="uptime_kuma_monitors",
        source="uptime_kuma",
        ok_summary="Uptime Kuma monitors are healthy.",
        issue_summary=f"{len(findings)} Uptime Kuma monitor issue(s) found.",
        evidence=evidence,
        findings=findings,
    )


def _dns_diagnostics(
    settings: AppSettings,
) -> tuple[list[EvidenceItem], list[DiagnosticFinding]]:
    evidence: list[EvidenceItem] = []
    findings: list[DiagnosticFinding] = []
    if settings.pihole.configured or settings.mock_mode:
        result = network_tool.pihole_summary(PiholeSummaryArgs())
        if result.success:
            data = _dict(result.data)
            evidence.append(
                EvidenceItem(
                    source="pihole_summary",
                    summary="Checked Pi-hole aggregate query and blocking counters.",
                    data={
                        "dns_queries_today": data.get("dns_queries_today"),
                        "ads_blocked_today": data.get("ads_blocked_today"),
                        "ads_percentage_today": data.get("ads_percentage_today"),
                        "domains_being_blocked": data.get("domains_being_blocked"),
                    },
                )
            )
            if _float(data.get("domains_being_blocked")) <= 0:
                findings.append(
                    _finding(
                        "Pi-hole blocklist appears empty",
                        "Pi-hole reports no domains being blocked.",
                        RiskLevel.MEDIUM,
                        "pihole_summary",
                        {"domains_being_blocked": data.get("domains_being_blocked")},
                        "Verify gravity/blocklist updates and Pi-hole health.",
                    )
                )
        else:
            findings.append(
                _finding(
                    "Pi-hole summary unavailable",
                    result.error or "Pi-hole summary request failed.",
                    RiskLevel.MEDIUM,
                    "pihole_summary",
                    {"error": result.error},
                    "Verify Pi-hole API connectivity.",
                )
            )
    if settings.unbound.configured or settings.mock_mode:
        result = network_tool.unbound_stats(UnboundStatsArgs())
        if result.success:
            data = _dict(result.data)
            evidence.append(
                EvidenceItem(
                    source="unbound_stats",
                    summary="Checked Unbound aggregate resolver statistics.",
                    data={
                        "total.num.queries": data.get("total.num.queries"),
                        "total.num.cachehits": data.get("total.num.cachehits"),
                        "total.requestlist.avg": data.get("total.requestlist.avg"),
                        "time.up": data.get("time.up"),
                    },
                )
            )
        else:
            findings.append(
                _finding(
                    "Unbound health unavailable",
                    result.error or "Unbound stats request failed.",
                    RiskLevel.MEDIUM,
                    "unbound_stats",
                    {"error": result.error},
                    "Verify unbound-control access from the worker host.",
                )
            )
    return evidence, findings


SCHEDULED_CHECKS: tuple[ScheduledCheckDefinition, ...] = (
    ScheduledCheckDefinition("container_health", "docker", _check_container_health, 5 * 60),
    ScheduledCheckDefinition("storage_thresholds", "storage", _check_storage_thresholds, 60 * 60),
    ScheduledCheckDefinition("arr_imports", "arr", _check_arr_imports, 15 * 60),
    ScheduledCheckDefinition("plex_db_health", "plex", _check_plex_db_health, 24 * 60 * 60),
    ScheduledCheckDefinition("rogue_macs", "network", _scan_rogue_macs, 15 * 60),
    ScheduledCheckDefinition(
        "uptime_kuma_monitors",
        "uptime_kuma",
        _check_uptime_kuma_monitors,
        5 * 60,
    ),
)


def _emit_check_result(result: ScheduledCheckResult) -> None:
    coroutine = store_check_result(result)
    try:
        asyncio.run(coroutine)
    except RuntimeError as exc:
        coroutine.close()
        logger.error("Could not store scheduled check result: %s", exc)
    except Exception as exc:  # pragma: no cover - store_event normally swallows Redis failures
        logger.error("Could not store scheduled check result: %s", exc)


def _skipped(check: str, source: str, reason: str) -> ScheduledCheckResult:
    return ScheduledCheckResult(
        check=check,
        source=source,
        status=CheckStatus.SKIPPED,
        severity="info",
        summary=reason,
        skipped_reason=reason,
        evidence=[EvidenceItem(source=source, summary=reason)],
    )


def _failed_tool_result(
    check: str, source: str, summary: str, error: str | None
) -> ScheduledCheckResult:
    return ScheduledCheckResult(
        check=check,
        source=source,
        status=CheckStatus.FAILED,
        severity="warning",
        summary=summary,
        evidence=[EvidenceItem(source=source, summary=error or summary)],
    )


def _result_from_findings(
    *,
    check: str,
    source: str,
    ok_summary: str,
    issue_summary: str,
    evidence: list[EvidenceItem],
    findings: list[DiagnosticFinding],
) -> ScheduledCheckResult:
    status, severity = _overall_status(findings)
    actions = [action for finding in findings for action in finding.suggested_actions]
    return ScheduledCheckResult(
        check=check,
        source=source,
        status=status,
        severity=severity,
        summary=issue_summary if findings else ok_summary,
        evidence=evidence,
        findings=findings,
        suggested_actions=actions,
    )


def _overall_status(findings: list[DiagnosticFinding]) -> tuple[CheckStatus, str]:
    if not findings:
        return CheckStatus.OK, "info"
    if any(finding.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL} for finding in findings):
        return CheckStatus.CRITICAL, "critical"
    return CheckStatus.WARNING, "warning"


def _finding(
    title: str,
    summary: str,
    risk: RiskLevel,
    source: str,
    data: dict[str, Any],
    action_description: str,
    *,
    requires_confirmation: bool = False,
) -> DiagnosticFinding:
    return DiagnosticFinding(
        title=title,
        summary=summary,
        risk=risk,
        confidence=ConfidenceLevel.HIGH,
        evidence=[EvidenceItem(source=source, summary=summary, data=data)],
        suggested_actions=[
            SuggestedAction(
                title="Review remediation",
                description=action_description,
                risk=risk,
                requires_confirmation=requires_confirmation,
            )
        ],
    )


def _risk_from_tool_severity(value: Any) -> RiskLevel:
    normalized = str(value or "").lower()
    if normalized in {"critical", "high"}:
        return RiskLevel.HIGH
    if normalized in {"warning", "warn", "medium", "degraded"}:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _configured_arr_services(settings: AppSettings) -> list[ArrService]:
    if settings.mock_mode:
        return [ArrService.SONARR, ArrService.RADARR]
    services: list[ArrService] = []
    if settings.sonarr.configured:
        services.append(ArrService.SONARR)
    if settings.radarr.configured:
        services.append(ArrService.RADARR)
    return services


def _arr_queue_findings(
    service: ArrService, records: list[dict[str, Any]]
) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for item in records:
        status = str(item.get("status") or "").lower()
        messages = _arr_status_messages(item)
        if status in {"warning", "error", "failed"} or messages:
            findings.append(
                _finding(
                    f"{service.value.title()} queue warning",
                    f"{item.get('title') or 'Queue item'} has queue status {status or 'unknown'}.",
                    RiskLevel.MEDIUM,
                    "arr_queue",
                    {
                        "service": service.value,
                        "queue_id": item.get("id"),
                        "title": item.get("title"),
                        "status": item.get("status"),
                        "tracked_messages": messages[:5],
                    },
                    "Inspect the queue item; removal or blocklisting requires confirmation.",
                    requires_confirmation=True,
                )
            )
        if _is_stale_queue_item(item):
            findings.append(
                _finding(
                    f"{service.value.title()} stale import queue item",
                    f"{item.get('title') or 'Queue item'} has been queued for more than 24 hours.",
                    RiskLevel.MEDIUM,
                    "arr_queue",
                    {
                        "service": service.value,
                        "queue_id": item.get("id"),
                        "title": item.get("title"),
                        "added": item.get("added"),
                    },
                    "Check downloader state and import paths before clearing the queue item.",
                    requires_confirmation=True,
                )
            )
    return findings


def _arr_health_findings(
    service: ArrService, rows: list[dict[str, Any]]
) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for row in rows:
        severity = str(row.get("type") or row.get("severity") or "").lower()
        if severity not in {"warning", "error"}:
            continue
        findings.append(
            _finding(
                f"{service.value.title()} health warning",
                str(row.get("message") or row.get("source") or "Health warning"),
                RiskLevel.HIGH if severity == "error" else RiskLevel.MEDIUM,
                "arr_health",
                {"service": service.value, **row},
                "Resolve the service health warning before retrying imports.",
            )
        )
    return findings


def _arr_import_findings(
    service: ArrService, data: dict[str, Any]
) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for mismatch in _list_of_dicts(data.get("mismatches")):
        findings.append(
            _finding(
                f"{service.value.title()} root-folder mismatch",
                (
                    f"{mismatch.get('title') or 'Queue item'} output path is outside "
                    "configured root folders."
                ),
                RiskLevel.MEDIUM,
                "arr_import_diagnosis",
                {"service": service.value, **mismatch},
                "Fix Docker volume mappings or root folders before retrying import.",
            )
        )
    return findings


def _plex_log_findings(data: dict[str, Any]) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for row in _list_of_dicts(data.get("findings")):
        category = str(row.get("category") or "plex_log_warning")
        findings.append(
            _finding(
                _title_from_type(category),
                str(row.get("line") or category),
                _risk_from_tool_severity(row.get("severity")),
                "plex_analyze_logs",
                row,
                "Inspect Plex logs and database health before restarting Plex.",
            )
        )
    return findings


def _storage_summary(row: dict[str, Any]) -> str:
    finding_type = str(row.get("type") or "storage_finding")
    if finding_type == "storage_threshold":
        return (
            f"{row.get('storage')} is {row.get('used_percent')}% full "
            f"(threshold {row.get('threshold_percent')}%)."
        )
    if finding_type == "backup_job_failed":
        return f"Backup job {row.get('job_id')} last state is {row.get('last_run_state')}."
    if finding_type == "backup_job_stale":
        return f"Backup job {row.get('job_id')} is stale."
    if finding_type == "local_filesystem_threshold":
        return f"{row.get('path')} is {row.get('used_percent')}% full."
    return finding_type


def _arr_status_messages(item: dict[str, Any]) -> list[str]:
    messages = item.get("statusMessages")
    out: list[str] = []
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict):
                continue
            for value in message.get("messages", []) or []:
                if isinstance(value, str):
                    out.append(value)
    return out


def _is_stale_queue_item(item: dict[str, Any]) -> bool:
    added = item.get("added")
    if not isinstance(added, str):
        return False
    try:
        parsed = datetime.fromisoformat(added.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds() > 24 * 3600


def _queue_records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        return _list_of_dicts(data.get("records"))
    return _list_of_dicts(data)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _title_from_type(value: str) -> str:
    return value.replace("_", " ").strip().title() or "Diagnostic Finding"


type CallableCheck = Callable[[AppSettings], ScheduledCheckResult]
