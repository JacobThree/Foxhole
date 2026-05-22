from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from agent.tools.base import ToolSafety
from agent.tools.registry import RegisteredTool

logger = logging.getLogger(__name__)

ArgumentCorrector = Callable[[str, str, str, dict[str, Any]], Awaitable[str]]


async def parse_tool_arguments(
    tool: RegisteredTool,
    raw_arguments: str,
    *,
    corrector: ArgumentCorrector | None = None,
    max_corrections: int = 1,
) -> BaseModel:
    current = raw_arguments
    last_error = ""
    for attempt in range(max_corrections + 1):
        try:
            return _validate(tool, current)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            last_error = str(exc)
            logger.info(
                "tool_argument_parse_failed",
                extra={"tool": tool.name, "attempt": attempt, "error": last_error},
            )
            if attempt >= max_corrections or corrector is None:
                break
            current = await corrector(tool.name, current, last_error, tool.schema())

    if tool.safety is ToolSafety.READ_ONLY:
        extracted = extract_balanced_json_object(raw_arguments)
        if extracted is not None and extracted != raw_arguments:
            logger.info("tool_argument_balanced_fallback", extra={"tool": tool.name})
            return _validate(tool, extracted)

    raise ValueError(f"Invalid arguments for {tool.name}: {last_error}")


def _validate(tool: RegisteredTool, raw_arguments: str) -> BaseModel:
    parsed = json.loads(raw_arguments)
    if not isinstance(parsed, dict):
        raise TypeError("Tool arguments must be a JSON object.")
    return tool.args_model.model_validate(parsed)


def extract_balanced_json_object(value: str) -> str | None:
    start = value.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(value[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return value[start : index + 1]
    return None
