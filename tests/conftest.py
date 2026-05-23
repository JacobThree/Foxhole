import os

import pytest


@pytest.fixture(autouse=True)
def clear_mock_mode_for_tests():
    """Tests opt into runtime mock mode explicitly."""
    original = os.environ.pop("FOXHOLE_MOCK_MODE", None)
    original_fixture = os.environ.pop("FOXHOLE_MOCK_FIXTURE_PATH", None)
    yield
    if original is not None:
        os.environ["FOXHOLE_MOCK_MODE"] = original
    if original_fixture is not None:
        os.environ["FOXHOLE_MOCK_FIXTURE_PATH"] = original_fixture
