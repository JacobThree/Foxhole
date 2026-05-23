from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent.settings import AppSettings
from workers import tasks

TASKS = {
    "container_health": tasks.check_container_health,
    "storage_thresholds": tasks.check_storage_thresholds,
    "arr_imports": tasks.check_arr_imports,
    "plex_db_health": tasks.check_plex_db_health,
    "rogue_macs": tasks.scan_rogue_macs,
}


def load_scenarios() -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parent.parent / "fixtures" / "eval-scenarios.json"
    with path.open() as handle:
        scenarios = json.load(handle)
    assert isinstance(scenarios, list)
    return [scenario for scenario in scenarios if isinstance(scenario, dict)]


def run_scenario(
    scenario: dict[str, Any],
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> dict[str, Any]:
    fixture_path = tmp_path / f"{scenario['name']}.json"
    fixture_path.write_text(json.dumps(scenario["fixture"]), encoding="utf-8")
    monkeypatch.setenv("FOXHOLE_MOCK_MODE", "1")
    monkeypatch.setenv("FOXHOLE_MOCK_FIXTURE_PATH", str(fixture_path))
    monkeypatch.setattr(tasks, "get_settings", lambda: AppSettings(mock_mode=True))
    monkeypatch.setattr(tasks, "_emit_check_result", lambda result: None)

    task = TASKS[str(scenario["check"])]
    result = task.run()
    assert isinstance(result, dict)
    return result


def assert_expected_diagnosis(scenario: dict[str, Any], result: dict[str, Any]) -> None:
    titles = {finding["title"] for finding in result.get("findings", [])}
    missing_findings = [
        title for title in scenario.get("expected_findings", []) if title not in titles
    ]
    assert not missing_findings, (
        f"{scenario['name']} missing expected findings {missing_findings}; got {sorted(titles)}"
    )

    evidence_sources = {item["source"] for item in result.get("evidence", [])}
    missing_evidence = [
        source
        for source in scenario.get("expected_evidence_sources", [])
        if source not in evidence_sources
    ]
    assert not missing_evidence, (
        f"{scenario['name']} missing expected evidence {missing_evidence}; "
        f"got {sorted(evidence_sources)}"
    )
