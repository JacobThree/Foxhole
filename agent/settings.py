import os
from functools import lru_cache
from typing import Any, Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_serializer
from pydantic_settings import BaseSettings, SettingsConfigDict


class IntegrationSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    enabled: bool = False
    base_url: AnyHttpUrl | None = None
    api_key: SecretStr | None = None
    token: SecretStr | None = None

    @property
    def configured(self) -> bool:
        return (
            self.enabled
            and self.base_url is not None
            and (self.api_key is not None or self.token is not None)
        )


class ProxmoxSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    enabled: bool = False
    host: str | None = None
    verify_ssl: bool = True
    token_id: SecretStr | None = None
    token_secret: SecretStr | None = None

    @property
    def configured(self) -> bool:
        return (
            self.enabled
            and self.host is not None
            and self.token_id is not None
            and self.token_secret is not None
        )


class DockerSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    enabled: bool = False
    socket_proxy_url: str | None = "tcp://docker-socket-proxy:2375"

    @property
    def configured(self) -> bool:
        return self.enabled and self.socket_proxy_url is not None


class TelegramSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    enabled: bool = False
    bot_token: SecretStr | None = None
    chat_id: str | None = None

    @property
    def configured(self) -> bool:
        return self.enabled and self.bot_token is not None and self.chat_id is not None


class UnboundSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    enabled: bool = False
    host: str | None = None
    port: int = Field(default=8953, ge=1, le=65535)

    @property
    def configured(self) -> bool:
        return self.enabled and self.host is not None


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FOXHOLE_",
        env_file=(".env", "/etc/homelab-agent/foxhole.env", "/etc/homelab-agent/config.env"),
        env_nested_delimiter="__",
        extra="ignore",
    )

    environment: str = "development"
    api_bearer_token: SecretStr | None = None
    session_cookie_secure: bool | None = None
    session_cookie_samesite: Literal["lax", "strict", "none"] | None = None
    session_cookie_name: str | None = None
    ui_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    redis_url: str = "redis://localhost:6379/0"

    llm_primary_model: str = "agent-primary"
    llm_primary_api_key: SecretStr | None = None
    llm_primary_api_base: str | None = None
    llm_local_model: str = "agent-local"
    llm_local_api_base: str | None = "http://localhost:11434"
    llm_vllm_model: str = "agent-vllm"
    llm_vllm_api_base: str | None = "http://localhost:8001/v1"
    llm_timeout_seconds: float = Field(default=30, ge=1, le=300)
    llm_retries: int = Field(default=2, ge=0, le=5)
    write_stage: int = Field(default=1, ge=1, le=3)
    write_confirmation_secret: SecretStr | None = None

    proxmox_enabled: bool = False
    proxmox_host: str | None = None
    proxmox_verify_ssl: bool = True
    proxmox_token_id: SecretStr | None = None
    proxmox_token_secret: SecretStr | None = None

    docker_enabled: bool = False
    docker_socket_proxy_url: str | None = "tcp://docker-socket-proxy:2375"

    telegram_enabled: bool = False
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None

    plex_enabled: bool = False
    plex_base_url: AnyHttpUrl | None = None
    plex_token: SecretStr | None = None
    plex_log_path: str | None = None

    sonarr_enabled: bool = False
    sonarr_base_url: AnyHttpUrl | None = None
    sonarr_api_key: SecretStr | None = None

    radarr_enabled: bool = False
    radarr_base_url: AnyHttpUrl | None = None
    radarr_api_key: SecretStr | None = None

    tautulli_enabled: bool = False
    tautulli_base_url: AnyHttpUrl | None = None
    tautulli_api_key: SecretStr | None = None

    overseerr_enabled: bool = False
    overseerr_base_url: AnyHttpUrl | None = None
    overseerr_api_key: SecretStr | None = None

    portainer_enabled: bool = False
    portainer_base_url: AnyHttpUrl | None = None
    portainer_api_token: SecretStr | None = None
    portainer_username: str | None = None
    portainer_password: SecretStr | None = None

    pihole_enabled: bool = False
    pihole_base_url: AnyHttpUrl | None = None
    pihole_api_token: SecretStr | None = None

    unbound_enabled: bool = False
    unbound_host: str | None = None
    unbound_port: int = Field(default=8953, ge=1, le=65535)

    network_allowed_subnets: list[str] = Field(default_factory=list)
    network_known_macs: list[str] = Field(default_factory=list)

    @field_serializer(
        "api_bearer_token",
        "llm_primary_api_key",
        "write_confirmation_secret",
        "proxmox_token_id",
        "proxmox_token_secret",
        "telegram_bot_token",
        "plex_token",
        "sonarr_api_key",
        "radarr_api_key",
        "tautulli_api_key",
        "overseerr_api_key",
        "portainer_api_token",
        "portainer_password",
        "pihole_api_token",
        when_used="json",
    )
    def serialize_secret(self, value: SecretStr | None) -> str | None:
        if value is None:
            return None
        return "********"

    @property
    def api_auth_configured(self) -> bool:
        return self.api_bearer_token is not None and bool(self.api_bearer_token.get_secret_value())

    @property
    def cookie_secure(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.environment.lower() in {"production", "https"}

    @property
    def cookie_samesite(self) -> Literal["lax", "strict", "none"]:
        if self.session_cookie_samesite is not None:
            return self.session_cookie_samesite
        return "strict" if self.cookie_secure else "lax"

    @property
    def cookie_name(self) -> str:
        if self.session_cookie_name is not None:
            return self.session_cookie_name
        return "__Host-foxhole_session" if self.cookie_secure else "foxhole_session"

    @property
    def proxmox(self) -> ProxmoxSettings:
        return ProxmoxSettings(
            enabled=self.proxmox_enabled,
            host=self.proxmox_host,
            verify_ssl=self.proxmox_verify_ssl,
            token_id=self.proxmox_token_id,
            token_secret=self.proxmox_token_secret,
        )

    @property
    def docker(self) -> DockerSettings:
        return DockerSettings(
            enabled=self.docker_enabled, socket_proxy_url=self.docker_socket_proxy_url
        )

    @property
    def telegram(self) -> TelegramSettings:
        return TelegramSettings(
            enabled=self.telegram_enabled,
            bot_token=self.telegram_bot_token,
            chat_id=self.telegram_chat_id,
        )

    @property
    def plex(self) -> IntegrationSettings:
        return IntegrationSettings(
            enabled=self.plex_enabled, base_url=self.plex_base_url, token=self.plex_token
        )

    @property
    def sonarr(self) -> IntegrationSettings:
        return IntegrationSettings(
            enabled=self.sonarr_enabled, base_url=self.sonarr_base_url, api_key=self.sonarr_api_key
        )

    @property
    def radarr(self) -> IntegrationSettings:
        return IntegrationSettings(
            enabled=self.radarr_enabled, base_url=self.radarr_base_url, api_key=self.radarr_api_key
        )

    @property
    def tautulli(self) -> IntegrationSettings:
        return IntegrationSettings(
            enabled=self.tautulli_enabled,
            base_url=self.tautulli_base_url,
            api_key=self.tautulli_api_key,
        )

    @property
    def overseerr(self) -> IntegrationSettings:
        return IntegrationSettings(
            enabled=self.overseerr_enabled,
            base_url=self.overseerr_base_url,
            api_key=self.overseerr_api_key,
        )

    @property
    def portainer_configured(self) -> bool:
        has_token = self.portainer_api_token is not None
        has_jwt_credentials = (
            self.portainer_username is not None and self.portainer_password is not None
        )
        return (
            self.portainer_enabled
            and self.portainer_base_url is not None
            and (has_token or has_jwt_credentials)
        )

    @property
    def pihole(self) -> IntegrationSettings:
        return IntegrationSettings(
            enabled=self.pihole_enabled, base_url=self.pihole_base_url, token=self.pihole_api_token
        )

    @property
    def unbound(self) -> UnboundSettings:
        return UnboundSettings(
            enabled=self.unbound_enabled, host=self.unbound_host, port=self.unbound_port
        )

    def integration_status(self) -> dict[str, bool]:
        return {
            "docker": self.docker.configured,
            "proxmox": self.proxmox.configured,
            "telegram": self.telegram.configured,
            "plex": self.plex.configured,
            "sonarr": self.sonarr.configured,
            "radarr": self.radarr.configured,
            "tautulli": self.tautulli.configured,
            "overseerr": self.overseerr.configured,
            "portainer": self.portainer_configured,
            "pihole": self.pihole.configured,
            "unbound": self.unbound.configured,
        }

    def integration_details(self) -> dict[str, dict[str, Any]]:
        return {
            "docker": self._integration_detail(
                self.docker_enabled,
                self.docker.configured,
                {"docker_socket_proxy_url": self.docker_socket_proxy_url is not None},
            ),
            "proxmox": self._integration_detail(
                self.proxmox_enabled,
                self.proxmox.configured,
                {
                    "proxmox_host": self.proxmox_host is not None,
                    "proxmox_token_id": self.proxmox_token_id is not None,
                    "proxmox_token_secret": self.proxmox_token_secret is not None,
                },
            ),
            "telegram": self._integration_detail(
                self.telegram_enabled,
                self.telegram.configured,
                {
                    "telegram_bot_token": self.telegram_bot_token is not None,
                    "telegram_chat_id": self.telegram_chat_id is not None,
                },
            ),
            "plex": self._integration_detail(
                self.plex_enabled,
                self.plex.configured,
                {
                    "plex_base_url": self.plex_base_url is not None,
                    "plex_token": self.plex_token is not None,
                },
            ),
            "sonarr": self._integration_detail(
                self.sonarr_enabled,
                self.sonarr.configured,
                {
                    "sonarr_base_url": self.sonarr_base_url is not None,
                    "sonarr_api_key": self.sonarr_api_key is not None,
                },
            ),
            "radarr": self._integration_detail(
                self.radarr_enabled,
                self.radarr.configured,
                {
                    "radarr_base_url": self.radarr_base_url is not None,
                    "radarr_api_key": self.radarr_api_key is not None,
                },
            ),
            "tautulli": self._integration_detail(
                self.tautulli_enabled,
                self.tautulli.configured,
                {
                    "tautulli_base_url": self.tautulli_base_url is not None,
                    "tautulli_api_key": self.tautulli_api_key is not None,
                },
            ),
            "overseerr": self._integration_detail(
                self.overseerr_enabled,
                self.overseerr.configured,
                {
                    "overseerr_base_url": self.overseerr_base_url is not None,
                    "overseerr_api_key": self.overseerr_api_key is not None,
                },
            ),
            "portainer": self._integration_detail(
                self.portainer_enabled,
                self.portainer_configured,
                {
                    "portainer_base_url": self.portainer_base_url is not None,
                    "portainer_credentials": self.portainer_api_token is not None
                    or (
                        self.portainer_username is not None
                        and self.portainer_password is not None
                    ),
                },
            ),
            "pihole": self._integration_detail(
                self.pihole_enabled,
                self.pihole.configured,
                {
                    "pihole_base_url": self.pihole_base_url is not None,
                    "pihole_api_token": self.pihole_api_token is not None,
                },
            ),
            "unbound": self._integration_detail(
                self.unbound_enabled,
                self.unbound.configured,
                {"unbound_host": self.unbound_host is not None},
            ),
        }

    def _integration_detail(
        self, enabled: bool, configured: bool, required: dict[str, bool]
    ) -> dict[str, Any]:
        return {
            "enabled": enabled,
            "configured": configured,
            "missing_configuration": [
                name for name, present in required.items() if enabled and not present
            ],
        }

    def redacted_summary(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "api_auth_configured": self.api_auth_configured,
            "redis_url": redact_url(self.redis_url),
            "llm": {
                "primary_model": self.llm_primary_model,
                "local_model": self.llm_local_model,
                "vllm_model": self.llm_vllm_model,
                "primary_api_key_configured": self.llm_primary_api_key is not None,
            },
            "integrations": self.integration_status(),
            "integration_details": self.integration_details(),
        }


def redact_url(value: str) -> str:
    if "@" not in value:
        return value
    scheme, rest = value.split("://", 1) if "://" in value else ("", value)
    host = rest.rsplit("@", 1)[1]
    return f"{scheme}://********@{host}" if scheme else f"********@{host}"


def update_env_file(updates: dict[str, str | None], env_path: str = ".env") -> None:
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()

    new_lines = []
    keys_updated = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0]
        if key in updates:
            val = updates[key]
            if val is not None:
                new_lines.append(f"{key}={val}\n")
            keys_updated.add(key)
        else:
            new_lines.append(line)

    for k, v in updates.items():
        if k not in keys_updated and v is not None:
            new_lines.append(f"{k}={v}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()


if __name__ == "__main__":
    settings = get_settings()
    print(settings.redacted_summary())
