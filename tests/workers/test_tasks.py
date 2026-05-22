from __future__ import annotations

from workers.tasks import (
    check_arr_imports,
    check_container_health,
    check_plex_db_health,
    check_storage_thresholds,
    scan_rogue_macs,
)


def test_tasks_return_structured_results() -> None:
    assert check_container_health.run() == {"status": "ok", "check": "container_health"}
    assert check_storage_thresholds.run() == {"status": "ok", "check": "storage_thresholds"}
    assert check_arr_imports.run() == {"status": "ok", "check": "arr_imports"}
    assert check_plex_db_health.run() == {"status": "ok", "check": "plex_db_health"}
    assert scan_rogue_macs.run() == {"status": "ok", "check": "rogue_macs"}
