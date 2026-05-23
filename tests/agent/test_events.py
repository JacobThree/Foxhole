from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agent.events import get_recent_events, store_event
from schemas.python.events import Event


@pytest.fixture
def mock_redis() -> Any:
    with patch("agent.events.get_redis") as mock_get_redis:
        mock_redis_instance = AsyncMock()
        mock_get_redis.return_value = mock_redis_instance
        yield mock_redis_instance


def test_store_event(mock_redis: Any) -> None:
    event = Event(type="alert", source="system", payload_summary="Test alert")
    asyncio.run(store_event(event))
    mock_redis.xadd.assert_called_once()
    mock_redis.aclose.assert_called_once()


def test_get_recent_events(mock_redis: Any) -> None:
    import json

    event = Event(type="alert", source="system", payload_summary="Test alert")
    mock_redis.xrevrange.return_value = [("12345-0", {"event": json.dumps(event.model_dump())})]

    events = asyncio.run(get_recent_events(limit=10))
    assert len(events) == 1
    assert events[0].payload_summary == "Test alert"
    mock_redis.xrevrange.assert_called_once_with(name="foxhole:events", max="+", min="-", count=10)
    mock_redis.aclose.assert_called_once()
