from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]

from agent.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "foxhole",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[],
)
celery_app.conf.update(
    task_default_queue="foxhole",
    task_track_started=True,
    timezone="UTC",
)
