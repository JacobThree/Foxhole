import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agent.tools.base import ToolResult
from schemas.python.events import Event


class MockMode:
    """
    Mock mode interceptor for running Foxhole UI and Backend locally
    without real homelab credentials.
    If FOXHOLE_MOCK_MODE=1, tools will return static data from tests/fixtures/mock-data.json.
    """

    @staticmethod
    def is_enabled() -> bool:
        return os.environ.get("FOXHOLE_MOCK_MODE", "").lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def get_mock_data(domain: str) -> dict[str, Any]:
        data = MockMode.load_fixture()
        result = data.get(domain, data.get("domains", {}).get(domain, {}))
        if isinstance(result, dict):
            return deepcopy(result)
        return {}

    @staticmethod
    def tool_result(
        tool_name: str,
        arguments: BaseModel | None = None,
        *,
        required: bool = True,
    ) -> ToolResult | None:
        if not MockMode.is_enabled():
            return None
        data = MockMode.tool_data(tool_name, arguments)
        if data is None:
            if not required:
                return None
            return ToolResult(
                success=False,
                error=f"Mock mode has no fixture for tool '{tool_name}'.",
            )
        if isinstance(data, dict) and "success" in data:
            return ToolResult.model_validate(data)
        return ToolResult(success=True, data=data)

    @staticmethod
    def tool_data(tool_name: str, arguments: BaseModel | None = None) -> Any:
        data = MockMode.load_fixture().get("tools", {})
        if not isinstance(data, dict):
            return None
        value = data.get(tool_name)
        if value is None:
            return None
        service = _argument_value(arguments, "service")
        if service is not None and isinstance(value, dict) and service in value:
            value = value[service]
        return deepcopy(value)

    @staticmethod
    def events(limit: int = 50) -> list[Event]:
        data = MockMode.load_fixture().get("events", [])
        if not isinstance(data, list):
            return []
        return [Event.model_validate(row) for row in data[:limit] if isinstance(row, dict)]

    @staticmethod
    def default_subnets() -> list[str]:
        data = MockMode.get_mock_data("network")
        subnets = data.get("allowed_subnets")
        if isinstance(subnets, list):
            return [str(subnet) for subnet in subnets]
        return ["192.168.1.0/24"]

    @staticmethod
    def default_plex_log_path() -> str:
        data = MockMode.get_mock_data("plex")
        path = data.get("log_path")
        return str(path) if path else "/mock/plex/Plex Media Server.log"

    @staticmethod
    def load_fixture() -> dict[str, Any]:
        path = os.environ.get("FOXHOLE_MOCK_FIXTURE_PATH")
        fixture_path = Path(path) if path else MockMode.default_fixture_path()
        try:
            import json

            with fixture_path.open() as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        if isinstance(data, dict):
            return data
        return {}

    @staticmethod
    def default_fixture_path() -> Path:
        return Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "mock-data.json"


def _argument_value(arguments: BaseModel | None, key: str) -> str | None:
    if arguments is None or not hasattr(arguments, key):
        return None
    value = getattr(arguments, key)
    if value is None:
        return None
    return str(getattr(value, "value", value))
