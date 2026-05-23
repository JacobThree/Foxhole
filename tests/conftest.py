import os

import pytest


@pytest.fixture(autouse=True)
def set_mock_mode_for_tests():
    """Ensure mock mode is enabled during all tests."""
    os.environ["FOXHOLE_MOCK_MODE"] = "1"
    yield
    # Note: If tests need real credentials, they should explicitly unset this.
