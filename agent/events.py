from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

from agent.settings import get_settings
from schemas.python.events import Event

logger = logging.getLogger(__name__)
STREAM_NAME = "foxhole:events"
MAX_LEN = 10000

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
