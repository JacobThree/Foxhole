from __future__ import annotations

from pathlib import Path

import pytest

from agent.settings import AppSettings
from schemas.python.caddy import CaddyListRoutesArgs, CaddyRouteDiagnosisArgs
from tools import caddy_tool


def test_parse_caddyfile_routes_extracts_reverse_proxy_upstreams() -> None:
    routes = caddy_tool.parse_caddyfile_routes(
        """
        plex.example.test {
          reverse_proxy plex:32400
        }

        sonarr.example.test {
          handle /api/* {
            reverse_proxy sonarr:8989
          }
        }
        """
    )

    assert routes == [
        {
            "source": "caddyfile",
            "route": "plex.example.test",
            "match": None,
            "upstreams": ["plex:32400"],
        },
        {
            "source": "caddyfile",
            "route": "sonarr.example.test",
            "match": "handle /api/*",
            "upstreams": ["sonarr:8989"],
        },
    ]


def test_list_routes_reads_configured_caddyfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caddyfile = tmp_path / "Caddyfile"
    caddyfile.write_text("plex.example.test {\n  reverse_proxy plex:32400\n}\n")
    monkeypatch.setattr(
        caddy_tool,
        "get_settings",
        lambda: AppSettings(caddy_enabled=True, caddy_config_path=str(caddyfile)),
    )

    result = caddy_tool.list_routes(CaddyListRoutesArgs(include_admin_config=False))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["route_count"] == 1
    assert result.data["routes"][0]["upstreams"] == ["plex:32400"]


def test_route_diagnosis_flags_missing_container(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        caddy_tool,
        "list_routes",
        lambda args: caddy_tool.ToolResult(
            success=True,
            data={
                "route_count": 1,
                "routes": [
                    {
                        "source": "caddyfile",
                        "route": "sonarr.example.test",
                        "match": None,
                        "upstreams": ["missing-sonarr:8989"],
                    }
                ],
            },
        ),
    )

    result = caddy_tool.route_diagnosis(
        CaddyRouteDiagnosisArgs(known_container_names=["plex", "sonarr"])
    )

    assert result.success is True
    assert result.data["finding_count"] == 1
    assert result.data["findings"][0]["type"] == "missing_container_upstream"


def test_caddy_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(caddy_tool, "get_settings", lambda: AppSettings())

    result = caddy_tool.list_routes(CaddyListRoutesArgs())

    assert result.success is False
    assert "not configured" in str(result.error)
