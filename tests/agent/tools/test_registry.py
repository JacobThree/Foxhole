from pydantic import BaseModel

from agent.tools.base import ToolResult, ToolSafety
from agent.tools.registry import ToolRegistry


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
