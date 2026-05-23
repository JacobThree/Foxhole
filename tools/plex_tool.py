from __future__ import annotations

import os
import re
from typing import Any
from xml.etree import ElementTree as ET

import httpx
from pydantic import BaseModel

from agent.settings import AppSettings, get_settings
from agent.tools.base import ToolResult
from agent.tools.registry import ToolRegistry
from schemas.python.plex import (
    PlexBufferingDiagnosisArgs,
    PlexDebugGuidanceArgs,
    PlexLogAnalysisArgs,
    PlexLogFinding,
    PlexSession,
    PlexSessionsArgs,
    PlexTranscodeStatusArgs,
)


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="plex_active_sessions",
        description=(
            "List active Plex sessions including user, title, player, decision, and "
            "hardware transcode state."
        ),
        args_model=PlexSessionsArgs,
    )(active_sessions)
    registry.register(
        name="plex_transcode_status",
        description="Summarize Plex transcode decisions and hardware acceleration usage.",
        args_model=PlexTranscodeStatusArgs,
    )(transcode_status)
    registry.register(
        name="plex_analyze_logs",
        description=(
            "Read a bounded Plex log file and detect SQLite busy, database locked, slow SQL, "
            "and transcode errors."
        ),
        args_model=PlexLogAnalysisArgs,
    )(analyze_logs)
    registry.register(
        name="plex_buffering_diagnosis",
        description=(
            "Combine active sessions and transcode signals to explain Plex buffering risk."
        ),
        args_model=PlexBufferingDiagnosisArgs,
    )(buffering_diagnosis)
    registry.register(
        name="plex_debug_guidance",
        description=(
            "Report whether Plex debug logging appears enabled and list safe manual commands "
            "for the operator to run next. Never toggles Plex settings."
        ),
        args_model=PlexDebugGuidanceArgs,
    )(debug_guidance)


def active_sessions(arguments: BaseModel) -> ToolResult:
    PlexSessionsArgs.model_validate(arguments)
    settings = get_settings()
    if not settings.plex.configured:
        return ToolResult(success=False, error="Plex integration is not configured.")
    try:
        with _client(settings) as client:
            response = client.get("/status/sessions")
            response.raise_for_status()
            sessions = _parse_sessions(response.text)
        return ToolResult(
            success=True,
            data={
                "session_count": len(sessions),
                "sessions": [session.model_dump(mode="json") for session in sessions],
            },
        )
    except httpx.HTTPError as exc:
        return ToolResult(success=False, error=f"Plex request failed: {exc}")


def transcode_status(arguments: BaseModel) -> ToolResult:
    PlexTranscodeStatusArgs.model_validate(arguments)
    result = active_sessions(PlexSessionsArgs())
    if not result.success or not isinstance(result.data, dict):
        return result
    sessions = [PlexSession.model_validate(row) for row in result.data.get("sessions", [])]
    transcoded = [s for s in sessions if s.decision.lower() == "transcode"]
    hardware = [s for s in transcoded if s.transcode_hardware]
    software = [s for s in transcoded if not s.transcode_hardware]
    total_bandwidth = sum(s.bandwidth_kbps for s in sessions if s.bandwidth_kbps is not None)
    return ToolResult(
        success=True,
        data={
            "session_count": len(sessions),
            "direct_play_count": sum(1 for s in sessions if s.decision.lower() == "directplay"),
            "direct_stream_count": sum(1 for s in sessions if s.decision.lower() == "directstream"),
            "transcode_count": len(transcoded),
            "hardware_transcode_count": len(hardware),
            "software_transcode_count": len(software),
            "total_bandwidth_kbps": round(total_bandwidth, 2),
            "hardware_transcode_available": _hardware_transcode_observed(sessions),
        },
    )


def analyze_logs(arguments: BaseModel) -> ToolResult:
    args = PlexLogAnalysisArgs.model_validate(arguments)
    try:
        text = _read_tail(args.log_path, args.max_bytes)
    except FileNotFoundError:
        return ToolResult(success=False, error=f"Plex log path is not available: {args.log_path}")
    except OSError as exc:
        return ToolResult(success=False, error=f"Could not read Plex log: {exc}")

    findings = _detect_findings(text, args.max_findings)
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1
    return ToolResult(
        success=True,
        data={
            "log_path": args.log_path,
            "bytes_read": len(text.encode()),
            "finding_counts": counts,
            "findings": [finding.model_dump(mode="json") for finding in findings],
        },
    )


def buffering_diagnosis(arguments: BaseModel) -> ToolResult:
    PlexBufferingDiagnosisArgs.model_validate(arguments)
    sessions_result = active_sessions(PlexSessionsArgs())
    if not sessions_result.success or not isinstance(sessions_result.data, dict):
        return sessions_result
    sessions = [PlexSession.model_validate(row) for row in sessions_result.data.get("sessions", [])]
    software_transcodes = [
        s for s in sessions if s.decision.lower() == "transcode" and not s.transcode_hardware
    ]
    high_bandwidth = [
        s for s in sessions if s.bandwidth_kbps is not None and s.bandwidth_kbps >= 20_000
    ]
    risk_factors: list[str] = []
    if software_transcodes:
        risk_factors.append(f"{len(software_transcodes)} session(s) using software transcoding")
    if len(sessions) >= 4:
        risk_factors.append(f"{len(sessions)} concurrent sessions")
    if high_bandwidth:
        risk_factors.append(f"{len(high_bandwidth)} session(s) above 20 Mbps stream bandwidth")
    risk = "high" if len(risk_factors) >= 2 else "elevated" if risk_factors else "low"
    return ToolResult(
        success=True,
        data={
            "risk": risk,
            "risk_factors": risk_factors,
            "session_count": len(sessions),
            "software_transcode_count": len(software_transcodes),
            "checks_to_run": [
                "CPU and GPU utilization on the Plex host",
                "Client codec support (HEVC, AV1) and direct-play eligibility",
                "Upstream bandwidth between server and remote clients",
                "Plex database health (see plex_analyze_logs)",
            ],
        },
    )


def debug_guidance(arguments: BaseModel) -> ToolResult:
    args = PlexDebugGuidanceArgs.model_validate(arguments)
    inspectable = False
    debug_observed: bool | None = None
    log_status = "not_provided"
    if args.log_path:
        try:
            text = _read_tail(args.log_path, 65_536)
            inspectable = True
            log_status = "readable"
            debug_observed = "DEBUG" in text or "Verbose" in text
        except FileNotFoundError:
            log_status = "missing"
        except OSError as exc:
            log_status = f"unreadable: {exc}"
    return ToolResult(
        success=True,
        data={
            "log_path": args.log_path,
            "log_status": log_status,
            "log_inspectable": inspectable,
            "debug_logging_observed": debug_observed,
            "manual_steps": [
                "Settings > General > Show Advanced > enable verbose logging in Plex.",
                "Restart Plex Media Server to apply the new log verbosity.",
                "Reproduce the issue, then run plex_analyze_logs against the same path.",
                "Settings > General > disable verbose logging when investigation is done.",
            ],
            "when_to_check": [
                "CPU and GPU utilization on the Plex host while playback runs",
                "Client codec support (HEVC, AV1) and direct-play eligibility",
                "Upstream bandwidth between server and remote clients",
                "Plex database health using plex_analyze_logs",
            ],
            "note": "Foxhole does not toggle Plex settings. Apply the manual steps above yourself.",
        },
    )


def _client(settings: AppSettings) -> httpx.Client:
    token = settings.plex_token.get_secret_value() if settings.plex_token else ""
    return httpx.Client(
        base_url=str(settings.plex_base_url),
        headers={"X-Plex-Token": token, "Accept": "application/xml"},
        timeout=10,
    )


def _parse_sessions(xml_text: str) -> list[PlexSession]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    sessions: list[PlexSession] = []
    for video in root.findall("Video"):
        sessions.append(_session_from_video(video))
    return sessions


def _session_from_video(video: ET.Element) -> PlexSession:
    user_element = video.find("User")
    player_element = video.find("Player")
    transcode = video.find("TranscodeSession")
    if transcode is None:
        decision = "directplay"
    else:
        video_decision = transcode.get("videoDecision") or ""
        audio_decision = transcode.get("audioDecision") or ""
        if video_decision == "copy" and audio_decision in {"copy", ""}:
            decision = "directstream"
        else:
            decision = "transcode"
    hardware = False
    video_codec = None
    audio_codec = None
    if transcode is not None:
        hardware = (transcode.get("transcodeHwRequested") == "1") or (
            transcode.get("transcodeHwFullPipeline") == "1"
        )
        video_codec = transcode.get("videoCodec")
        audio_codec = transcode.get("audioCodec")
    bandwidth = None
    session = video.find("Session")
    if session is not None:
        bandwidth = _float_or_none(session.get("bandwidth"))
    return PlexSession(
        user=user_element.get("title") if user_element is not None else None,
        title=video.get("title"),
        player=player_element.get("product") if player_element is not None else None,
        player_address=player_element.get("address") if player_element is not None else None,
        decision=decision,
        transcode_hardware=hardware,
        transcode_video_codec=video_codec,
        transcode_audio_codec=audio_codec,
        bandwidth_kbps=bandwidth,
    )


def _hardware_transcode_observed(sessions: list[PlexSession]) -> bool:
    return any(s.transcode_hardware for s in sessions if s.decision.lower() == "transcode")


def _read_tail(path: str, max_bytes: int) -> str:
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        if size > max_bytes:
            handle.seek(size - max_bytes)
        data = handle.read()
    return data.decode(errors="replace")


_LOG_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("sqlite_busy", "warning", re.compile(r"database is locked", re.IGNORECASE)),
    ("sqlite_busy", "warning", re.compile(r"SQLITE_BUSY", re.IGNORECASE)),
    ("slow_sql", "warning", re.compile(r"slow SQL.*\d+ms", re.IGNORECASE)),
    ("transcode_error", "critical", re.compile(r"Transcoder.*(error|failed)", re.IGNORECASE)),
    ("transcode_error", "critical", re.compile(r"ERROR.*Transcode", re.IGNORECASE)),
    ("database_warning", "warning", re.compile(r"DB.*(corrupt|repair)", re.IGNORECASE)),
]


def _detect_findings(text: str, max_findings: int) -> list[PlexLogFinding]:
    findings: list[PlexLogFinding] = []
    for line in text.splitlines():
        for category, severity, pattern in _LOG_PATTERNS:
            if pattern.search(line):
                findings.append(
                    PlexLogFinding(category=category, severity=severity, line=line.strip()[:500])
                )
                break
        if len(findings) >= max_findings:
            break
    return findings


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
