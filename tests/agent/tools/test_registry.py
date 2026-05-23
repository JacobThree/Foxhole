from pydantic import BaseModel, SecretStr

from agent.settings import AppSettings
from agent.tools.base import ToolResult, ToolSafety
from agent.tools.registry import (
    ToolIntent,
    ToolRegistry,
    classify_tool_intents,
    integration_capabilities,
    integration_manifests,
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


def test_schemas_preserves_explicit_empty_selection() -> None:
    registry = ToolRegistry()

    @registry.register(name="echo", description="Echo a value.", args_model=EchoArgs)
    def echo(arguments: BaseModel) -> ToolResult:
        return ToolResult(success=True, data=arguments.model_dump())

    assert registry.schemas([]) == []


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


def test_registered_tools_expose_stable_capability_metadata() -> None:
    settings = AppSettings(
        docker_enabled=True,
        docker_socket_proxy_url="tcp://docker-socket-proxy:2375",
        sonarr_enabled=True,
        sonarr_base_url="http://sonarr.local:8989",
        sonarr_api_key=SecretStr("secret-key"),
    )
    registry = ToolRegistry()
    register_builtin_tools(registry, settings=settings)

    tools = registry.list()
    by_name = {tool.name: tool for tool in tools}

    assert all(tool.capability_ids for tool in tools)
    assert by_name["docker_list_containers"].integration == "docker"
    assert by_name["docker_list_containers"].category == "read"
    assert by_name["docker_list_containers"].capability_ids == ["containers.list"]
    assert by_name["arr_queue_item_action"].category == "write"
    assert by_name["arr_queue_item_action"].capability_ids == ["media.arr.queue.confirmed"]


def test_integration_manifests_include_mcp_ready_metadata() -> None:
    settings = AppSettings(
        docker_enabled=True,
        docker_socket_proxy_url="tcp://docker-socket-proxy:2375",
        plex_enabled=True,
        plex_base_url="http://plex.local:32400",
        plex_token=SecretStr("secret-token"),
    )
    registry = ToolRegistry()
    register_builtin_tools(registry, settings=settings)

    manifests = integration_manifests(settings, registry)
    by_id = {manifest.id: manifest for manifest in manifests}

    docker = by_id["docker"]
    assert docker.name == "Docker"
    assert docker.category == "containers"
    assert docker.config_schema["required"] == ["docker_socket_proxy_url"]
    assert docker.resource_uris == ["foxhole://docker/containers"]
    assert any(tool.name == "docker_list_containers" for tool in docker.tools)
    assert any(
        capability.capability_ids == ["containers.list"] for capability in docker.capabilities
    )
    assert "MCP" in docker.mcp_adapter_notes
    assert "secret-token" not in str([manifest.model_dump() for manifest in manifests])


def test_caddy_manifest_exposes_reverse_proxy_resources() -> None:
    settings = AppSettings(caddy_enabled=True, caddy_config_path="/etc/caddy/Caddyfile")
    registry = ToolRegistry()
    register_builtin_tools(registry, settings=settings)

    by_id = {manifest.id: manifest for manifest in integration_manifests(settings, registry)}

    assert by_id["caddy"].category == "reverse_proxy"
    assert by_id["caddy"].resource_uris == ["foxhole://reverse-proxy/caddy/routes"]
    assert any(
        "reverse_proxy.routes.read" in capability.capability_ids
        for capability in by_id["caddy"].capabilities
    )


def test_intent_classification_scopes_media_tools() -> None:
    settings = AppSettings(
        docker_enabled=True,
        plex_enabled=True,
        plex_base_url="http://plex.local:32400",
        plex_token=SecretStr("secret-token"),
        sonarr_enabled=True,
        sonarr_base_url="http://sonarr.local:8989",
        sonarr_api_key=SecretStr("secret-key"),
        tautulli_enabled=True,
        tautulli_base_url="http://tautulli.local:8181",
        tautulli_api_key=SecretStr("tautulli-key"),
        pihole_enabled=True,
        pihole_base_url="http://pihole.local/admin",
        pihole_api_token=SecretStr("pihole-key"),
    )
    registry = ToolRegistry()
    register_builtin_tools(registry, settings=settings)

    selected_names = {tool.name for tool in registry.list_for_message("Why is Plex buffering?")}

    assert ToolIntent.MEDIA in classify_tool_intents("Why is Plex buffering?")
    assert "plex_active_sessions" in selected_names
    assert "docker_list_containers" in selected_names
    assert "tautulli_recent_history" in selected_names
    assert "network_pihole_summary" not in selected_names


def test_intent_classification_scopes_network_tools() -> None:
    settings = AppSettings(
        docker_enabled=True,
        pihole_enabled=True,
        pihole_base_url="http://pihole.local/admin",
        pihole_api_token=SecretStr("pihole-key"),
        unbound_enabled=True,
        unbound_host="unbound.local",
    )
    registry = ToolRegistry()
    register_builtin_tools(registry, settings=settings)

    selected_names = {tool.name for tool in registry.list_for_message("Find rogue MACs on LAN")}

    assert ToolIntent.NETWORK in classify_tool_intents("Find rogue MACs on LAN")
    assert "network_unknown_devices" in selected_names
    assert "security_posture" in selected_names
    assert "docker_list_containers" not in selected_names


def test_unknown_intent_falls_back_to_read_only_tools() -> None:
    registry = ToolRegistry()

    @registry.register(name="lookup", description="Lookup.", args_model=EchoArgs)
    def lookup(arguments: BaseModel) -> ToolResult:
        return ToolResult(success=True, data=arguments.model_dump())

    @registry.register(
        name="restart",
        description="Restart.",
        args_model=EchoArgs,
        safety=ToolSafety.REQUIRES_CONFIRMATION,
    )
    def restart(arguments: BaseModel) -> ToolResult:
        return ToolResult(success=True, data=arguments.model_dump())

    selected_names = {tool.name for tool in registry.list_for_message("What changed yesterday?")}

    assert selected_names == {"lookup"}
