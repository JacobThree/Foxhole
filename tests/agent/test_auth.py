from fastapi.testclient import TestClient
from pydantic import SecretStr

from agent.main import app, check_redis_ready
from agent.settings import AppSettings, get_settings


def _settings() -> AppSettings:
    return AppSettings(api_bearer_token=SecretStr("test-token"))


async def _redis_ready() -> bool:
    return True


def test_protected_route_rejects_missing_bearer_token() -> None:
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[check_redis_ready] = _redis_ready
    client = TestClient(app)

    response = client.get("/readyz")

    app.dependency_overrides.clear()
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token."


def test_protected_route_rejects_invalid_bearer_token() -> None:
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[check_redis_ready] = _redis_ready
    client = TestClient(app)

    response = client.get("/readyz", headers={"Authorization": "Bearer wrong"})

    app.dependency_overrides.clear()
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid bearer token."

