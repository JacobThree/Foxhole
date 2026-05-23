from pydantic import BaseModel, SecretStr

from agent.settings import AppSettings
from agent.tools.base import ToolResult, ToolSafety
from agent.tools.registry import (
    ToolRegistry,
    integration_capabilities,
    register_builtin_tools,
)


class EchoArgs(BaseModel):
    value: str


def test_registry_exports_openai_compatible_schema() -> None:
    registry = ToolRegistry()

    @registry.register(
        name="echo",
        description="Echo a value.",
        args_model=EchoArgs,
        safety=ToolSafety.READ_ONLY,
    )
    def echo(arguments: BaseModel) -> ToolResult:
        args = EchoArgs.model_validate(arguments)
        return ToolResult(success=True, data={"value": args.value})

    schemas = registry.schemas()

    assert len(registry.list()) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "echo"
    assert schemas[0]["function"]["parameters"]["properties"]["value"]["type"] == "string"


def test_duplicate_tool_names_fail() -> None:
    registry = ToolRegistry()

    @registry.register(name="echo", description="First.", args_model=EchoArgs)
    def first(arguments: BaseModel) -> ToolResult:
        return ToolResult(success=True, data=arguments.model_dump())

    try:
        registry.add(registry.get("echo"))
    except ValueError as exc:
        assert "Duplicate tool name" in str(exc)
    else:
        raise AssertionError("duplicate registration should fail")


def test_tool_result_has_stable_envelope() -> None:
    result = ToolResult(success=False, error="failed")

    assert result.model_dump()["success"] is False
    assert result.model_dump()["data"] is None
    assert result.model_dump()["error"] == "failed"
    assert result.model_dump()["write_action"]["requested"] is False


def test_integration_capabilities_follow_configuration_without_secrets() -> None:
    settings = AppSettings(
        docker_enabled=True,
        docker_socket_proxy_url="tcp://docker-socket-proxy:2375",
        sonarr_enabled=True,
        sonarr_base_url="http://sonarr.local:8989",
        sonarr_api_key=SecretStr("secret-key"),
    )
    registry = ToolRegistry()
    register_builtin_tools(registry, settings=settings)

    capabilities = integration_capabilities(settings, registry)
    by_name = {item.integration: item for item in capabilities}

    assert by_name["docker"].configured is True
    assert any(
        capability.tool_name == "docker_list_containers"
        for capability in by_name["docker"].capabilities
    )
    assert by_name["plex"].enabled is False
    assert by_name["plex"].capabilities == []
    assert by_name["sonarr"].missing_configuration == []
    assert "secret-key" not in str([item.model_dump() for item in capabilities])
