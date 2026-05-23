from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

from agent.settings import get_settings
from schemas.python.events import CheckSummary, Event

logger = logging.getLogger(__name__)
STREAM_NAME = "foxhole:events"
MAX_LEN = 10000
KNOWN_SEVERITIES = ("info", "warning", "critical")


async def get_redis() -> Any:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def store_event(event: Event) -> None:
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


async def get_recent_events(limit: int = 50) -> list[Event]:
    try:
        redis = await get_redis()
        # XREVRANGE to get newest first
        messages = await redis.xrevrange(name=STREAM_NAME, max="+", min="-", count=limit)
        events = []
        for _message_id, fields in messages:
            if "event" in fields:
                event_data = json.loads(fields["event"])
                events.append(Event(**event_data))
        await redis.aclose()
        return events
    except Exception as e:
        logger.error(f"Failed to fetch events from Redis: {e}")
        return []


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
