from __future__ import annotations

import asyncio
import threading
import time

from agent.scheduler import InProcessScheduler, SchedulerJob, build_scheduler_jobs, create_scheduler
from agent.settings import AppSettings


def test_build_scheduler_jobs_registers_current_check_cadence() -> None:
    jobs = build_scheduler_jobs(AppSettings())

    intervals = {job.name: job.interval_seconds for job in jobs}
    assert intervals["container_health"] == 5 * 60
    assert intervals["storage_thresholds"] == 60 * 60
    assert intervals["arr_imports"] == 15 * 60
    assert intervals["plex_db_health"] == 24 * 60 * 60
    assert intervals["rogue_macs"] == 15 * 60
    assert intervals["uptime_kuma_monitors"] == 5 * 60
    assert intervals["retention_prune"] == 24 * 60 * 60


def test_create_scheduler_returns_none_when_disabled() -> None:
    assert create_scheduler(AppSettings(runtime_mode="distributed")) is None
    assert create_scheduler(AppSettings(scheduler_enabled=False)) is None


def test_run_once_uses_shared_scheduled_check(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr("agent.scheduler.run_scheduled_check", lambda name: calls.append(name))
    scheduler = create_scheduler(AppSettings(scheduler_job_timeout_seconds=1))

    assert scheduler is not None
    asyncio.run(scheduler.run_once("container_health"))

    assert calls == ["container_health"]


def test_scheduler_skips_overlapping_job_runs() -> None:
    calls = 0

    def slow_job() -> None:
        nonlocal calls
        calls += 1
        time.sleep(0.05)

    async def run_concurrent_jobs() -> None:
        scheduler = InProcessScheduler(
            (SchedulerJob("slow", 60, slow_job),),
            job_timeout_seconds=1,
        )
        await asyncio.gather(scheduler.run_once("slow"), scheduler.run_once("slow"))

    asyncio.run(run_concurrent_jobs())

    assert calls == 1


def test_scheduler_keeps_timed_out_job_marked_running() -> None:
    calls = 0
    release = threading.Event()

    def slow_job() -> None:
        nonlocal calls
        calls += 1
        release.wait(timeout=1)

    async def run_timed_out_job() -> None:
        scheduler = InProcessScheduler(
            (SchedulerJob("slow", 60, slow_job),),
            job_timeout_seconds=0.01,
        )
        await scheduler.run_once("slow")
        await scheduler.run_once("slow")
        assert calls == 1

        release.set()
        for _ in range(20):
            if not scheduler._running_jobs:
                break
            await asyncio.sleep(0.01)

        await scheduler.run_once("slow")

    asyncio.run(run_timed_out_job())

    assert calls == 2
