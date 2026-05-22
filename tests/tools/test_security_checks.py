from __future__ import annotations

from typing import Any

import pytest

from agent.settings import AppSettings
from schemas.python.security import SecurityPostureArgs
from tools import security_tool


def test_security_checks_detects_privileged_container(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockContainer:
        def __init__(self, name: str, privileged: bool):
            self.name = name
            self.attrs = {
                "HostConfig": {
                    "Privileged": privileged,
                    "RestartPolicy": {"Name": "unless-stopped"}
                }
            }
            
    class MockClient:
        class containers:
            @staticmethod
            def list(all: bool) -> list[Any]:
                return [
                    MockContainer("safe-app", False),
                    MockContainer("risk-app", True),
                ]

    class MockDocker:
        @staticmethod
        def DockerClient(base_url: Any = None) -> Any:
            return MockClient()

    monkeypatch.setattr(security_tool, "get_settings", lambda: AppSettings())
    monkeypatch.setattr(security_tool, "importlib", type("mock_importlib", (), {"import_module": lambda name: MockDocker() if name == "docker" else None}))
    
    result = security_tool.security_posture(SecurityPostureArgs())
    
    assert result.success is True
    assert isinstance(result.data, dict)
    findings = result.data["findings"]
    
    high_findings = [f for f in findings if f["severity"] == "high"]
    assert len(high_findings) == 1
    assert "risk-app" in high_findings[0]["evidence"]
