from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from agent.db.repositories import prune_durable_history
from agent.settings import AppSettings, get_settings
from workers.tasks import run_scheduled_check, scheduled_check_definitions

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerJob:
    name: str
    interval_seconds: float
    run: Callable[[], Any]


class InProcessScheduler:
    def __init__(
        self,
        jobs: tuple[SchedulerJob, ...],
        *,
        job_timeout_seconds: float,
    ) -> None:
        self.jobs = jobs
        self.job_timeout_seconds = job_timeout_seconds
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self._running_jobs: dict[str, concurrent.futures.Future[Any] | asyncio.Future[Any]] = {}

    async def start(self) -> None:
        if self._tasks:
            return
        self._stop_event.clear()
        self._tasks = [
            asyncio.create_task(self._run_loop(job), name=f"foxhole-scheduler-{job.name}")
            for job in self.jobs
        ]
        logger.info("Started in-process scheduler with %d job(s)", len(self.jobs))

    async def stop(self) -> None:
        if not self._tasks:
            return
        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        logger.info("Stopped in-process scheduler")

    async def run_once(self, job_name: str) -> None:
        job = self._job_by_name(job_name)
        await self._run_job(job)

    async def _run_loop(self, job: SchedulerJob) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=job.interval_seconds)
            except TimeoutError:
                await self._run_job(job)
            except asyncio.CancelledError:
                raise

    async def _run_job(self, job: SchedulerJob) -> None:
        running_job = self._running_jobs.get(job.name)
        if running_job is not None and not running_job.done():
            logger.warning("Skipping overlapping scheduled job: %s", job.name)
            return

        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(None, job.run)
        self._running_jobs[job.name] = future
        try:
            await asyncio.wait_for(asyncio.shield(future), timeout=self.job_timeout_seconds)
        except TimeoutError:
            logger.error("Scheduled job timed out: %s", job.name)
            future.add_done_callback(lambda done: self._clear_timed_out_job(job.name, done))
        except Exception:
            logger.exception("Scheduled job failed: %s", job.name)
        finally:
            if future.done():
                self._running_jobs.pop(job.name, None)

    def _clear_timed_out_job(
        self,
        job_name: str,
        future: concurrent.futures.Future[Any] | asyncio.Future[Any],
    ) -> None:
        if self._running_jobs.get(job_name) is not future:
            return
        self._running_jobs.pop(job_name, None)
        try:
            future.result()
        except Exception:
            logger.exception("Scheduled job failed after timeout: %s", job_name)

    def _job_by_name(self, job_name: str) -> SchedulerJob:
        for job in self.jobs:
            if job.name == job_name:
                return job
        raise ValueError(f"Unknown scheduler job: {job_name}")


def build_scheduler_jobs(settings: AppSettings | None = None) -> tuple[SchedulerJob, ...]:
    runtime_settings = settings or get_settings()
    check_jobs = tuple(
        SchedulerJob(
            name=definition.name,
            interval_seconds=definition.interval_seconds,
            run=partial(run_scheduled_check, definition.name),
        )
        for definition in scheduled_check_definitions()
    )
    retention_job = SchedulerJob(
        name="retention_prune",
        interval_seconds=24 * 60 * 60,
        run=partial(prune_durable_history, runtime_settings),
    )
    return (*check_jobs, retention_job)


def create_scheduler(settings: AppSettings | None = None) -> InProcessScheduler | None:
    runtime_settings = settings or get_settings()
    if runtime_settings.runtime_mode != "single" or not runtime_settings.scheduler_enabled:
        return None
    return InProcessScheduler(
        build_scheduler_jobs(runtime_settings),
        job_timeout_seconds=runtime_settings.scheduler_job_timeout_seconds,
    )
