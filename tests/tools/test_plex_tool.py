from __future__ import annotations

import httpx
from pydantic import SecretStr

from agent.settings import AppSettings
from agent.tools.registry import ToolRegistry
from schemas.python.plex import (
    PlexBufferingDiagnosisArgs,
    PlexLogAnalysisArgs,
    PlexSessionsArgs,
    PlexTranscodeStatusArgs,
)
from tools import plex_tool

SESSIONS_XML = """
<MediaContainer size="2">
  <Video title="Andor" type="episode">
    <User title="alice"/>
    <Player product="Plex Web" address="10.0.0.5"/>
    <Media videoResolution="1080"/>
    <TranscodeSession videoDecision="transcode" audioDecision="copy"
                      videoCodec="h264" audioCodec="aac"
                      transcodeHwRequested="1" transcodeHwFullPipeline="1"/>
    <Session bandwidth="24000"/>
  </Video>
  <Video title="Severance" type="episode">
    <User title="bob"/>
    <Player product="Apple TV" address="10.0.0.6"/>
    <Media videoResolution="1080"/>
    <TranscodeSession videoDecision="transcode" audioDecision="transcode"
                      videoCodec="h264" audioCodec="aac"
                      transcodeHwRequested="0" transcodeHwFullPipeline="0"/>
    <Session bandwidth="9000"/>
  </Video>
</MediaContainer>
"""


def _settings() -> AppSettings:
    return AppSettings(plex_base_url="http://plex.local:32400", plex_token=SecretStr("tok"))


def _patch_client(monkeypatch, transport: httpx.MockTransport) -> None:
    monkeypatch.setattr(plex_tool, "get_settings", _settings)
    monkeypatch.setattr(
        plex_tool,
        "_client",
        lambda settings: httpx.Client(
            base_url=str(settings.plex_base_url),
            headers={"X-Plex-Token": "tok"},
            transport=transport,
        ),
    )


def test_plex_tools_register_expected_names() -> None:
    registry = ToolRegistry()
    plex_tool.register_tools(registry)

    assert {tool.name for tool in registry.list()} == {
        "plex_active_sessions",
        "plex_transcode_status",
        "plex_analyze_logs",
        "plex_buffering_diagnosis",
    }


def test_active_sessions_parses_user_title_player_decision(monkeypatch) -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=SESSIONS_XML))
    _patch_client(monkeypatch, transport)

    result = plex_tool.active_sessions(PlexSessionsArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["session_count"] == 2
    first = result.data["sessions"][0]
    assert first["user"] == "alice"
    assert first["title"] == "Andor"
    assert first["player"] == "Plex Web"
    assert first["decision"] == "transcode"
    assert first["transcode_hardware"] is True
    assert first["bandwidth_kbps"] == 24000.0


def test_transcode_status_counts_hardware_and_software(monkeypatch) -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=SESSIONS_XML))
    _patch_client(monkeypatch, transport)

    result = plex_tool.transcode_status(PlexTranscodeStatusArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["transcode_count"] == 2
    assert result.data["hardware_transcode_count"] == 1
    assert result.data["software_transcode_count"] == 1
    assert result.data["hardware_transcode_available"] is True
    assert result.data["total_bandwidth_kbps"] == 33000.0


def test_buffering_diagnosis_flags_software_transcode_and_bandwidth(monkeypatch) -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=SESSIONS_XML))
    _patch_client(monkeypatch, transport)

    result = plex_tool.buffering_diagnosis(PlexBufferingDiagnosisArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["software_transcode_count"] == 1
    assert any("software" in factor for factor in result.data["risk_factors"])


def test_analyze_logs_detects_sqlite_and_transcode_errors(tmp_path) -> None:
    log = tmp_path / "Plex Media Server.log"
    log.write_text(
        "\n".join(
            [
                "Jan 01 09:00:00 INFO startup",
                "Jan 01 09:00:01 WARN database is locked",
                "Jan 01 09:00:02 ERROR Transcoder failed to start",
                "Jan 01 09:00:03 slow SQL took 1500ms",
                "Jan 01 09:00:04 normal line",
            ]
        )
    )

    result = plex_tool.analyze_logs(
        PlexLogAnalysisArgs(log_path=str(log), max_bytes=4096, max_findings=10)
    )

    assert result.success is True
    assert isinstance(result.data, dict)
    counts = result.data["finding_counts"]
    assert counts["sqlite_busy"] == 1
    assert counts["transcode_error"] == 1
    assert counts["slow_sql"] == 1


def test_analyze_logs_missing_path_returns_unavailable(tmp_path) -> None:
    result = plex_tool.analyze_logs(
        PlexLogAnalysisArgs(log_path=str(tmp_path / "missing.log"))
    )

    assert result.success is False
    assert "not available" in (result.error or "")


def test_active_sessions_requires_configured_plex(monkeypatch) -> None:
    monkeypatch.setattr(plex_tool, "get_settings", lambda: AppSettings())

    result = plex_tool.active_sessions(PlexSessionsArgs())

    assert result.success is False
    assert "not configured" in (result.error or "")
