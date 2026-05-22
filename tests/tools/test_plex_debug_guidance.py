from __future__ import annotations

from schemas.python.plex import PlexDebugGuidanceArgs
from tools import plex_tool


def test_debug_guidance_without_log_path_reports_not_provided() -> None:
    result = plex_tool.debug_guidance(PlexDebugGuidanceArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["log_status"] == "not_provided"
    assert result.data["log_inspectable"] is False
    assert result.data["debug_logging_observed"] is None
    assert any("verbose logging" in step.lower() for step in result.data["manual_steps"])


def test_debug_guidance_detects_verbose_keyword(tmp_path) -> None:
    log = tmp_path / "Plex Media Server.log"
    log.write_text("INFO ready\nDEBUG fetching item 42\n")

    result = plex_tool.debug_guidance(PlexDebugGuidanceArgs(log_path=str(log)))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["log_status"] == "readable"
    assert result.data["log_inspectable"] is True
    assert result.data["debug_logging_observed"] is True


def test_debug_guidance_missing_log_reports_missing(tmp_path) -> None:
    result = plex_tool.debug_guidance(
        PlexDebugGuidanceArgs(log_path=str(tmp_path / "missing.log"))
    )

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["log_status"] == "missing"
    assert result.data["log_inspectable"] is False


def test_debug_guidance_does_not_imply_automatic_mutation() -> None:
    result = plex_tool.debug_guidance(PlexDebugGuidanceArgs())

    assert result.success is True
    assert isinstance(result.data, dict)
    note = result.data["note"]
    assert "does not toggle" in note.lower()
