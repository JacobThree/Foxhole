import asyncio

from pydantic import BaseModel, Field

from agent.tools.argument_parsing import parse_tool_arguments
from agent.tools.base import ToolResult, ToolSafety
from agent.tools.registry import ToolRegistry


class LookupArgs(BaseModel):
    name: str
    limit: int = Field(ge=1, le=20)


def _tool(safety: ToolSafety = ToolSafety.READ_ONLY):
    registry = ToolRegistry()

    @registry.register(
        name="lookup",
        description="Lookup things.",
        args_model=LookupArgs,
        safety=safety,
    )
    def lookup(arguments: BaseModel) -> ToolResult:
        return ToolResult(success=True, data=arguments.model_dump())

    return registry.get("lookup")


def test_valid_arguments_parse_without_correction() -> None:
    args = asyncio.run(parse_tool_arguments(_tool(), '{"name": "plex", "limit": 5}'))

    assert isinstance(args, LookupArgs)
    assert args.name == "plex"
    assert args.limit == 5


def test_invalid_arguments_retry_with_correction() -> None:
    async def correct(tool_name: str, raw: str, error: str, schema: dict) -> str:
        assert tool_name == "lookup"
        assert raw == '{"name": "plex", "limit": 99}'
        assert "less than or equal" in error
        assert schema["properties"]["limit"]["maximum"] == 20
        return '{"name": "plex", "limit": 10}'

    args = asyncio.run(
        parse_tool_arguments(
            _tool(),
            '{"name": "plex", "limit": 99}',
            corrector=correct,
            max_corrections=1,
        )
    )

    assert LookupArgs.model_validate(args).limit == 10


def test_balanced_object_fallback_only_for_read_only_tools() -> None:
    args = asyncio.run(
        parse_tool_arguments(_tool(), 'call lookup with {"name": "sonarr", "limit": 2}')
    )

    assert LookupArgs.model_validate(args).name == "sonarr"

    try:
        asyncio.run(
            parse_tool_arguments(
                _tool(ToolSafety.REQUIRES_CONFIRMATION),
                'call lookup with {"name": "sonarr", "limit": 2}',
            )
        )
    except ValueError as exc:
        assert "Invalid arguments" in str(exc)
    else:
        raise AssertionError("write tool fallback should be rejected")
