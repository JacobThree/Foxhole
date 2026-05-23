from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.evals.helpers import assert_expected_diagnosis, load_scenarios, run_scenario


@pytest.mark.parametrize("scenario", load_scenarios(), ids=lambda scenario: scenario["name"])
def test_broken_homelab_scenario_expected_diagnosis(
    scenario: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = run_scenario(scenario, monkeypatch=monkeypatch, tmp_path=tmp_path)

    assert result["status"] in {"warning", "critical"}
    assert_expected_diagnosis(scenario, result)
