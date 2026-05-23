from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]
from celery.schedules import crontab  # type: ignore[import-untyped]

from agent.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "foxhole",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.tasks"],
)
celery_app.conf.update(
    task_default_queue="foxhole",
    task_routes={
        "tasks.scan_rogue_macs": {"queue": "scan"},
    },
    task_track_started=True,
    timezone="UTC",
    task_annotations={"*": {"rate_limit": "10/s", "max_retries": 3, "retry_backoff": True}},
    beat_schedule={
        "check-container-health": {
            "task": "tasks.check_container_health",
            "schedule": crontab(minute="*/5"),
        },
        "check-storage-thresholds": {
            "task": "tasks.check_storage_thresholds",
            "schedule": crontab(minute="0"),
        },
        "check-arr-imports": {
            "task": "tasks.check_arr_imports",
            "schedule": crontab(minute="*/15"),
        },
        "check-plex-db-health": {
            "task": "tasks.check_plex_db_health",
            "schedule": crontab(minute="0", hour="2"),
        },
        "scan-rogue-macs": {
            "task": "tasks.scan_rogue_macs",
            "schedule": crontab(minute="*/15"),
        },
    },
)
