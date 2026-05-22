from __future__ import annotations

import httpx
from pydantic import SecretStr

from agent.settings import AppSettings
from schemas.python.portainer import PortainerListEndpointsArgs
from tools import portainer_tool


def test_api_token_auth_takes_precedence() -> None:
    settings = AppSettings(
        portainer_base_url="http://portainer.local",
        portainer_api_token=SecretStr("token"),
        portainer_username="user",
        portainer_password=SecretStr("password"),
    )

    assert portainer_tool._auth_headers(settings) == {"X-API-Key": "token"}


def test_list_endpoints_uses_portainer_api(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"] == "token"
        assert request.url.path == "/api/endpoints"
        return httpx.Response(200, json=[{"Id": 1, "Name": "local"}])

    transport = httpx.MockTransport(handler)

    def client(settings: AppSettings) -> httpx.Client:
        return httpx.Client(
            base_url=str(settings.portainer_base_url),
            headers={"X-API-Key": "token"},
            transport=transport,
        )

    monkeypatch.setattr(
        portainer_tool,
        "get_settings",
        lambda: AppSettings(
            portainer_base_url="http://portainer.local",
            portainer_api_token=SecretStr("token"),
        ),
    )
    monkeypatch.setattr(portainer_tool, "_client", client)

    result = portainer_tool.list_endpoints(PortainerListEndpointsArgs())

    assert result.success is True
    assert result.data == [{"Id": 1, "Name": "local"}]


def test_403_is_reported_as_denied(monkeypatch) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(403, json={"message": "denied"}))

    def client(settings: AppSettings) -> httpx.Client:
        return httpx.Client(base_url=str(settings.portainer_base_url), transport=transport)

    monkeypatch.setattr(
        portainer_tool,
        "get_settings",
        lambda: AppSettings(
            portainer_base_url="http://portainer.local",
            portainer_api_token=SecretStr("token"),
        ),
    )
    monkeypatch.setattr(portainer_tool, "_client", client)

    result = portainer_tool.list_endpoints(PortainerListEndpointsArgs())

    assert result.success is False
    assert result.error == "Portainer denied this request."
