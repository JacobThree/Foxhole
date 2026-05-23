import json
import os
from typing import Any


class MockMode:
    """
    Mock mode interceptor for running Foxhole UI and Backend locally
    without real homelab credentials.
    If FOXHOLE_MOCK_MODE=1, tools will return static data from tests/fixtures/mock-data.json.
    """

    @staticmethod
    def is_enabled() -> bool:
        return os.environ.get("FOXHOLE_MOCK_MODE") == "1"

    @staticmethod
    def get_mock_data(domain: str) -> dict[str, Any]:
        fixture_path = os.path.join(
            os.path.dirname(__file__), "..", "tests", "fixtures", "mock-data.json"
        )
        try:
            with open(fixture_path) as f:
                data = json.load(f)
                result = data.get(domain, {})
                if isinstance(result, dict):
                    return result
                return {}
        except FileNotFoundError:
            return {}
