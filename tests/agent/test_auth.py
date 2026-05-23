from fastapi.testclient import TestClient
from pydantic import SecretStr

from agent.main import app, check_redis_ready
from agent.settings import AppSettings, get_settings


def _settings() -> AppSettings:
    return AppSettings(api_bearer_token=SecretStr("test-token"))


def _https_settings() -> AppSettings:
    return AppSettings(
        api_bearer_token=SecretStr("test-token"),
        session_cookie_secure=True,
        session_cookie_samesite="strict",
    )


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


def test_login_sets_http_only_session_cookie_for_protected_routes() -> None:
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[check_redis_ready] = _redis_ready
    client = TestClient(app)

    login = client.post("/auth/login", json={"bearer_token": "test-token"})
    ready = client.get("/readyz")

    app.dependency_overrides.clear()
    assert login.status_code == 200
    assert login.json() == {"authenticated": True, "cookie_name": "foxhole_session"}
    assert "httponly" in login.headers["set-cookie"].lower()
    assert "samesite=lax" in login.headers["set-cookie"].lower()
    assert "secure" not in login.headers["set-cookie"].lower()
    assert ready.status_code == 200


def test_logout_clears_session_cookie() -> None:
    app.dependency_overrides[get_settings] = _settings
    client = TestClient(app)

    client.post("/auth/login", json={"bearer_token": "test-token"})
    logout = client.post("/auth/logout")
    response = client.get("/readyz")

    app.dependency_overrides.clear()
    assert logout.status_code == 200
    assert "foxhole_session" in logout.headers["set-cookie"]
    assert response.status_code == 401


def test_https_cookie_profile_uses_host_cookie_and_strict_samesite() -> None:
    app.dependency_overrides[get_settings] = _https_settings
    client = TestClient(app)

    response = client.post("/auth/login", json={"bearer_token": "test-token"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["cookie_name"] == "__Host-foxhole_session"
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie
    assert "samesite=strict" in cookie
