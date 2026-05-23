from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

from agent.db.repositories import EventRepository
from agent.settings import get_settings
from schemas.python.events import CheckSummary, Event, ScheduledCheckResult

logger = logging.getLogger(__name__)
STREAM_NAME = "foxhole:events"
MAX_LEN = 10000
KNOWN_SEVERITIES = ("info", "warning", "critical")


async def get_redis() -> Any:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def store_event(event: Event) -> None:
    try:
        EventRepository().store_event(event)
    except Exception as e:
        logger.error(f"Failed to store event to SQLite: {e}")

    try:
        redis = await get_redis()
        # Redact secrets from data if necessary (basic implementation)
        data_str = json.dumps(event.model_dump())
        await redis.xadd(
            name=STREAM_NAME,
            fields={"event": data_str},
            maxlen=MAX_LEN,
            approximate=True,
        )
        await redis.aclose()
    except Exception as e:
        logger.error(f"Failed to store event to Redis: {e}")


def event_from_check_result(result: ScheduledCheckResult) -> Event:
    return Event(
        type="scheduled_check",
        severity=normalize_severity(result.severity),
        source=result.source,
        payload_summary=result.summary,
        correlation_id=result.correlation_id,
        data={
            "check": result.check,
            "status": result.status.value,
            "duration_ms": result.duration_ms,
            "skipped_reason": result.skipped_reason,
            "evidence": [item.model_dump(mode="json") for item in result.evidence],
            "suggested_actions": [
                action.model_dump(mode="json") for action in result.suggested_actions
            ],
        },
        findings=result.findings,
    )


async def store_check_result(result: ScheduledCheckResult) -> Event:
    event = event_from_check_result(result)
    try:
        EventRepository().store_check_result(result)
    except Exception as e:
        logger.error(f"Failed to store check result to SQLite: {e}")
    await store_event(event)
    return event


async def get_recent_events(limit: int = 50) -> list[Event]:
    durable_events = EventRepository().recent_events(limit=limit)
    try:
        redis = await get_redis()
        # XREVRANGE to get newest first
        messages = await redis.xrevrange(name=STREAM_NAME, max="+", min="-", count=limit)
        redis_events = []
        for _message_id, fields in messages:
            if "event" in fields:
                event_data = json.loads(fields["event"])
                redis_events.append(Event(**event_data))
        await redis.aclose()
        return _merge_recent_events(redis_events, durable_events, limit)
    except Exception as e:
        logger.error(f"Failed to fetch events from Redis: {e}")
        return durable_events


def _merge_recent_events(
    redis_events: list[Event],
    durable_events: list[Event],
    limit: int,
) -> list[Event]:
    merged: dict[str, Event] = {}
    for event in durable_events:
        merged[event.id] = event
    for event in redis_events:
        merged[event.id] = event
    return sorted(merged.values(), key=lambda event: event.timestamp, reverse=True)[:limit]


def normalize_severity(severity: str | None) -> str:
    value = (severity or "info").lower()
    if value in {"critical", "error", "high"}:
        return "critical"
    if value in {"warning", "warn", "medium", "degraded"}:
        return "warning"
    return "info"


def severity_counts(events: list[Event]) -> dict[str, int]:
    counts = {severity: 0 for severity in KNOWN_SEVERITIES}
    for event in events:
        counts[normalize_severity(event.severity)] += 1
    return counts


def latest_check_summaries(events: list[Event], limit: int = 5) -> list[CheckSummary]:
    summaries: list[CheckSummary] = []
    for event in events:
        event_type = event.type.lower()
        if "check" not in event_type and "diagnostic" not in event_type:
            continue
        status = str(event.data.get("status") or normalize_severity(event.severity))
        summaries.append(
            CheckSummary(
                id=event.id,
                timestamp=event.timestamp,
                source=event.source,
                status=status,
                severity=normalize_severity(event.severity),
                summary=event.payload_summary,
                correlation_id=event.correlation_id,
            )
        )
        if len(summaries) >= limit:
            break
    return summaries
