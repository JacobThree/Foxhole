from __future__ import annotations

import logging
from typing import Any

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.check_container_health")  # type: ignore[untyped-decorator]
def check_container_health() -> dict[str, Any]:
    logger.info("Checking container health")
    return {"status": "ok", "check": "container_health"}


@celery_app.task(name="tasks.check_storage_thresholds")  # type: ignore[untyped-decorator]
def check_storage_thresholds() -> dict[str, Any]:
    logger.info("Checking storage thresholds")
    return {"status": "ok", "check": "storage_thresholds"}


@celery_app.task(name="tasks.check_arr_imports")  # type: ignore[untyped-decorator]
def check_arr_imports() -> dict[str, Any]:
    logger.info("Checking *Arr imports")
    return {"status": "ok", "check": "arr_imports"}


@celery_app.task(name="tasks.check_plex_db_health")  # type: ignore[untyped-decorator]
def check_plex_db_health() -> dict[str, Any]:
    logger.info("Checking Plex DB health")
    return {"status": "ok", "check": "plex_db_health"}


@celery_app.task(name="tasks.scan_rogue_macs")  # type: ignore[untyped-decorator]
def scan_rogue_macs() -> dict[str, Any]:
    logger.info("Scanning for rogue MACs")
    return {"status": "ok", "check": "rogue_macs"}
