from fastapi.testclient import TestClient
from pydantic import SecretStr

from agent import __version__
from agent.main import app, check_redis_ready
from agent.settings import AppSettings, get_settings


def _settings() -> AppSettings:
    return AppSettings(
        api_bearer_token=SecretStr("test-token"), docker_enabled=True, telegram_enabled=True,
        redis_url="redis://:redis-secret@redis.local:6379/0",
        sonarr_enabled=True, sonarr_base_url="http://sonarr.local:8989",
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

