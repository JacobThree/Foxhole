from fastapi.testclient import TestClient
from pydantic import SecretStr

from agent import __version__
from agent.db.repositories import AuditRepository, EventRepository
from agent.main import app, check_redis_ready
from agent.settings import AppSettings, get_settings
from schemas.python.events import AuditReceipt, Event


def _settings() -> AppSettings:
    return AppSettings(
        api_bearer_token=SecretStr("test-token"),
        docker_enabled=True,
        telegram_enabled=True,
        redis_url="redis://:redis-secret@redis.local:6379/0",
        sonarr_enabled=True,
        sonarr_base_url="http://sonarr.local:8989",
        sonarr_api_key=SecretStr("sonarr-secret"),
    )


async def _redis_ready() -> bool:
    return True


async def _redis_not_ready() -> bool:
    return False


def test_healthz_is_public() -> None:
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "foxhole", "version": __version__}


def test_readyz_returns_redacted_status() -> None:
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[check_redis_ready] = _redis_ready
    client = TestClient(app)

    response = client.get("/readyz", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["checks"] == {"settings": True, "redis": True}
    assert body["settings"]["redis_url"] == "redis://********@redis.local:6379/0"
    assert body["settings"]["integrations"]["sonarr"] is True
    assert "sonarr-secret" not in response.text
    assert "redis-secret" not in response.text


def test_readyz_returns_503_when_redis_is_unavailable() -> None:
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[check_redis_ready] = _redis_not_ready
    client = TestClient(app)

    response = client.get("/readyz", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["detail"]["checks"]["redis"] is False


def test_update_settings_persists_and_clears_cache(monkeypatch) -> None:
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[check_redis_ready] = lambda: True
    client = TestClient(app)

    # We mock update_env_file to avoid writing to actual .env
    calls = []

    def mock_update_env_file(updates, env_path=".env"):
        calls.append(updates)

    monkeypatch.setattr("agent.settings.update_env_file", mock_update_env_file)

    payload = {
        "updates": {
            "plex_enabled": True,
            "plex_base_url": "http://new-plex.local",
            "plex_token": None,
        }
    }
    response = client.patch(
        "/settings", json=payload, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0]["FOXHOLE_PLEX_ENABLED"] == "true"
    assert calls[0]["FOXHOLE_PLEX_BASE_URL"] == "http://new-plex.local"
    assert calls[0]["FOXHOLE_PLEX_TOKEN"] is None


def test_dashboard_summary_returns_read_only_control_plane_state(monkeypatch) -> None:
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[check_redis_ready] = _redis_ready
    client = TestClient(app)

    async def mock_recent_events(limit: int = 50):
        return [
            Event(
                type="scheduled_check",
                severity="warning",
                source="sonarr",
                payload_summary="Import queue is stale.",
                data={"status": "warning"},
            ),
            Event(
                type="alert",
                severity="critical",
                source="docker",
                payload_summary="Container restart loop.",
            ),
        ]

    monkeypatch.setattr("agent.events.get_recent_events", mock_recent_events)

    response = client.get("/dashboard/summary", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["readiness"] == {"settings": True, "redis": True}
    assert body["severity_counts"] == {"info": 0, "warning": 1, "critical": 1}
    assert body["latest_checks"][0]["source"] == "sonarr"
    assert body["recent_events"][0]["payload_summary"] == "Import queue is stale."
    assert any(
        integration["name"] == "sonarr" and integration["configured"] is True
        for integration in body["integrations"]
    )


def test_capabilities_endpoint_hides_raw_configuration() -> None:
    app.dependency_overrides[get_settings] = _settings
    client = TestClient(app)

    response = client.get("/capabilities", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    sonarr = next(item for item in body if item["integration"] == "sonarr")
    assert sonarr["configured"] is True
    assert any(capability["tool_name"] == "arr_queue" for capability in sonarr["capabilities"])
    assert "sonarr-secret" not in response.text


def test_audits_endpoint_returns_redacted_safety_receipts(tmp_path) -> None:
    settings = _settings().model_copy(update={"database_path": str(tmp_path / "foxhole.db")})
    AuditRepository(settings).create(
        AuditReceipt(
            id="audit-1",
            timestamp="2026-05-22T00:00:00+00:00",
            tool_name="restart_container",
            caller="api",
            arguments={"container": "plex", "api_key": "********"},
            safety="requires_confirmation",
            confirmation_status="denied_stage_1",
            result="denied",
        )
    )
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    response = client.get("/audits", headers={"Authorization": "Bearer test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == "audit-1"
    assert body[0]["arguments"]["api_key"] == "********"


def test_incidents_endpoint_groups_warning_events_and_returns_timeline(tmp_path) -> None:
    settings = _settings().model_copy(update={"database_path": str(tmp_path / "foxhole.db")})
    repository = EventRepository(settings)
    repository.store_event(
        Event(
            id="event-1",
            timestamp="2026-05-22T00:00:00+00:00",
            type="scheduled_check",
            severity="warning",
            source="plex",
            payload_summary="Plex buffering risk is elevated.",
            correlation_id="plex-corr",
        )
    )
    repository.store_event(
        Event(
            id="event-2",
            timestamp="2026-05-22T00:05:00+00:00",
            type="scheduled_check",
            severity="critical",
            source="plex",
            payload_summary="Plex transcode failures detected.",
            correlation_id="plex-corr",
        )
    )
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    list_response = client.get("/incidents", headers={"Authorization": "Bearer test-token"})
    incident_id = list_response.json()[0]["id"]
    detail_response = client.get(
        f"/incidents/{incident_id}",
        headers={"Authorization": "Bearer test-token"},
    )

    app.dependency_overrides.clear()
    assert list_response.status_code == 200
    assert list_response.json()[0]["event_count"] == 2
    assert list_response.json()[0]["severity"] == "critical"
    assert detail_response.status_code == 200
    assert [entry["event_id"] for entry in detail_response.json()["timeline"]] == [
        "event-1",
        "event-2",
    ]
