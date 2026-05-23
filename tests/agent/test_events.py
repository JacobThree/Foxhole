from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agent.db.repositories import AuditRepository, prune_durable_history
from agent.events import (
    event_from_check_result,
    get_recent_events,
    latest_check_summaries,
    severity_counts,
    store_check_result,
    store_event,
)
from agent.settings import AppSettings, get_settings
from schemas.python.chat import EvidenceItem, SuggestedAction
from schemas.python.events import AuditReceipt, CheckStatus, Event, ScheduledCheckResult


@pytest.fixture
def isolated_database(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOXHOLE_DATABASE_PATH", str(tmp_path / "foxhole.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_redis() -> Any:
    with patch("agent.events.get_redis") as mock_get_redis:
        mock_redis_instance = AsyncMock()
        mock_get_redis.return_value = mock_redis_instance
        yield mock_redis_instance


def test_store_event(isolated_database: None, mock_redis: Any) -> None:
    event = Event(type="alert", source="system", payload_summary="Test alert")
    asyncio.run(store_event(event))
    mock_redis.xadd.assert_called_once()
    mock_redis.aclose.assert_called_once()


def test_check_result_converts_to_scheduled_check_event() -> None:
    result = ScheduledCheckResult(
        check="container_health",
        source="docker",
        status=CheckStatus.WARNING,
        severity="warning",
        summary="1 Docker issue found",
        evidence=[EvidenceItem(source="docker", summary="Checked 2 containers")],
        suggested_actions=[SuggestedAction(title="Review container", description="Inspect logs")],
        duration_ms=12.5,
        correlation_id="corr-1",
    )

    event = event_from_check_result(result)

    assert event.type == "scheduled_check"
    assert event.source == "docker"
    assert event.correlation_id == "corr-1"
    assert event.data["status"] == "warning"
    assert event.data["evidence"][0]["summary"] == "Checked 2 containers"
    assert event.data["suggested_actions"][0]["title"] == "Review container"


def test_store_check_result_uses_event_stream(isolated_database: None, mock_redis: Any) -> None:
    result = ScheduledCheckResult(
        check="container_health",
        source="docker",
        status=CheckStatus.OK,
        summary="Docker containers are healthy",
    )

    event = asyncio.run(store_check_result(result))

    assert event.type == "scheduled_check"
    mock_redis.xadd.assert_called_once()
    mock_redis.aclose.assert_called_once()


def test_get_recent_events(isolated_database: None, mock_redis: Any) -> None:
    import json

    event = Event(type="alert", source="system", payload_summary="Test alert")
    mock_redis.xrevrange.return_value = [("12345-0", {"event": json.dumps(event.model_dump())})]

    events = asyncio.run(get_recent_events(limit=10))
    assert len(events) == 1
    assert events[0].payload_summary == "Test alert"
    mock_redis.xrevrange.assert_called_once_with(name="foxhole:events", max="+", min="-", count=10)
    mock_redis.aclose.assert_called_once()


def test_recent_events_fall_back_to_durable_storage(
    isolated_database: None,
    mock_redis: Any,
) -> None:
    event = Event(type="alert", source="system", payload_summary="Survives restart")
    asyncio.run(store_event(event))
    mock_redis.xrevrange.side_effect = RuntimeError("redis unavailable")

    events = asyncio.run(get_recent_events(limit=10))

    assert len(events) == 1
    assert events[0].id == event.id
    assert events[0].payload_summary == "Survives restart"


def test_retention_pruning_removes_only_expired_durable_history(
    isolated_database: None,
    mock_redis: Any,
) -> None:
    settings = AppSettings(database_path=get_settings().database_path, event_retention_days=30)
    old_timestamp = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    new_timestamp = datetime.now(UTC).isoformat()
    asyncio.run(
        store_event(
            Event(
                id="old-event",
                timestamp=old_timestamp,
                type="alert",
                source="system",
                payload_summary="old",
            )
        )
    )
    asyncio.run(
        store_event(
            Event(
                id="new-event",
                timestamp=new_timestamp,
                type="alert",
                source="system",
                payload_summary="new",
            )
        )
    )
    AuditRepository(settings).create(
        AuditReceipt(
            id="old-audit",
            timestamp=old_timestamp,
            tool_name="restart_container",
            caller="test",
            arguments={},
            safety="requires_confirmation",
            confirmation_status="denied_stage_1",
            result="denied",
        )
    )

    deleted = prune_durable_history(settings)
    mock_redis.xrevrange.side_effect = RuntimeError("redis unavailable")
    events = asyncio.run(get_recent_events(limit=10))

    assert deleted["events"] == 1
    assert deleted["audits"] == 0
    assert [event.id for event in events] == ["new-event"]


def test_event_summary_helpers_normalize_severity_and_checks() -> None:
    events = [
        Event(type="scheduled_check", source="docker", severity="high", payload_summary="Looping"),
        Event(type="alert", source="plex", severity="warn", payload_summary="Buffering"),
        Event(type="tool_call", source="chat", severity="info", payload_summary="Inspected"),
    ]

    assert severity_counts(events) == {"info": 1, "warning": 1, "critical": 1}

    checks = latest_check_summaries(events)
    assert len(checks) == 1
    assert checks[0].source == "docker"
    assert checks[0].severity == "critical"
