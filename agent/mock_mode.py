import json
import os


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
    def get_mock_data(domain: str) -> dict:
        fixture_path = os.path.join(
            os.path.dirname(__file__), 
            "..", "tests", "fixtures", "mock-data.json"
        )
        try:
            with open(fixture_path) as f:
                data = json.load(f)
                return data.get(domain, {})
        except FileNotFoundError:
            return {}
