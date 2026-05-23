from functools import lru_cache
from typing import Any

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
        return self.enabled and self.base_url is not None and (self.api_key is not None or self.token is not None)


class ProxmoxSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    enabled: bool = False
    host: str | None = None
    verify_ssl: bool = True
    token_id: SecretStr | None = None
    token_secret: SecretStr | None = None

    @property
    def configured(self) -> bool:
        return self.enabled and self.host is not None and self.token_id is not None and self.token_secret is not None


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
        return DockerSettings(enabled=self.docker_enabled, socket_proxy_url=self.docker_socket_proxy_url)

    @property
    def telegram(self) -> TelegramSettings:
        return TelegramSettings(enabled=self.telegram_enabled, bot_token=self.telegram_bot_token, chat_id=self.telegram_chat_id)

    @property
    def plex(self) -> IntegrationSettings:
        return IntegrationSettings(enabled=self.plex_enabled, base_url=self.plex_base_url, token=self.plex_token)

    @property
    def sonarr(self) -> IntegrationSettings:
        return IntegrationSettings(enabled=self.sonarr_enabled, base_url=self.sonarr_base_url, api_key=self.sonarr_api_key)

    @property
    def radarr(self) -> IntegrationSettings:
        return IntegrationSettings(enabled=self.radarr_enabled, base_url=self.radarr_base_url, api_key=self.radarr_api_key)

    @property
    def tautulli(self) -> IntegrationSettings:
        return IntegrationSettings(enabled=self.tautulli_enabled, base_url=self.tautulli_base_url, api_key=self.tautulli_api_key)

    @property
    def overseerr(self) -> IntegrationSettings:
        return IntegrationSettings(enabled=self.overseerr_enabled, base_url=self.overseerr_base_url, api_key=self.overseerr_api_key)

    @property
    def portainer_configured(self) -> bool:
        has_token = self.portainer_api_token is not None
        has_jwt_credentials = (
            self.portainer_username is not None and self.portainer_password is not None
        )
        return self.portainer_enabled and self.portainer_base_url is not None and (has_token or has_jwt_credentials)

    @property
    def pihole(self) -> IntegrationSettings:
        return IntegrationSettings(enabled=self.pihole_enabled, base_url=self.pihole_base_url, token=self.pihole_api_token)

    @property
    def unbound(self) -> UnboundSettings:
        return UnboundSettings(enabled=self.unbound_enabled, host=self.unbound_host, port=self.unbound_port)

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
        }


def redact_url(value: str) -> str:
    if "@" not in value:
        return value
    scheme, rest = value.split("://", 1) if "://" in value else ("", value)
    host = rest.rsplit("@", 1)[1]
    return f"{scheme}://********@{host}" if scheme else f"********@{host}"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()


if __name__ == "__main__":
    settings = get_settings()
    print(settings.redacted_summary())
