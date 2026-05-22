from pydantic import SecretStr

from agent.settings import AppSettings, get_settings, redact_url


def test_valid_core_and_optional_integration_config(monkeypatch) -> None:
    monkeypatch.setenv("FOXHOLE_API_BEARER_TOKEN", "dev-token")
    monkeypatch.setenv("FOXHOLE_REDIS_URL", "redis://:secret@redis.local:6379/0")
    monkeypatch.setenv("FOXHOLE_PLEX_BASE_URL", "http://plex.local:32400")
    monkeypatch.setenv("FOXHOLE_PLEX_TOKEN", "plex-secret")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.api_auth_configured is True
    assert settings.plex.configured is True
    assert settings.integration_status()["plex"] is True
    assert settings.redacted_summary()["redis_url"] == "redis://********@redis.local:6379/0"


def test_missing_optional_integrations_do_not_disable_core_settings() -> None:
    settings = AppSettings(api_bearer_token=SecretStr("dev-token"))

    status = settings.integration_status()

    assert settings.api_auth_configured is True
    assert status["proxmox"] is False
    assert status["sonarr"] is False
    assert status["radarr"] is False


def test_secret_redaction_excludes_raw_values() -> None:
    settings = AppSettings(
        api_bearer_token=SecretStr("api-secret"),
        llm_primary_api_key=SecretStr("llm-secret"),
        proxmox_token_secret=SecretStr("proxmox-secret"),
        telegram_bot_token=SecretStr("telegram-secret"),
    )

    dumped = settings.model_dump_json()
    summary = settings.redacted_summary()

    assert "api-secret" not in dumped
    assert "llm-secret" not in dumped
    assert "proxmox-secret" not in dumped
    assert "telegram-secret" not in dumped
    assert summary["api_auth_configured"] is True


def test_redact_url_without_credentials_is_stable() -> None:
    assert redact_url("redis://localhost:6379/0") == "redis://localhost:6379/0"

