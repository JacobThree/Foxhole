from __future__ import annotations

from agent.tools.registry import ToolRegistry
from schemas.python.docker import DockerReadLogsArgs, DockerRestartLoopArgs
from tools import docker_tool


class FakeImage:
    short_id = "sha256:abc123"
    tags = ["plex:latest"]


class FakeContainer:
    id = "abcdef1234567890"
    name = "plex"
    image = FakeImage()
    status = "running"

    def __init__(self, restart_count: int = 0) -> None:
        self.attrs = {
            "Config": {"Image": "plex:latest", "Labels": {"app": "plex"}},
            "State": {
                "Status": self.status,
                "Health": {"Status": "healthy"},
                "RestartCount": restart_count,
            },
            "NetworkSettings": {
                "Ports": {"32400/tcp": [{"HostIp": "127.0.0.1", "HostPort": "32400"}]}
            },
        }

    def logs(self, *, tail: int, stdout: bool, stderr: bool) -> bytes:
        assert tail == 2
        assert stdout is True
        assert stderr is True
        return b"line one\nline two\nline three\n"


class FakeContainers:
    def __init__(self) -> None:
        self.container = FakeContainer(restart_count=4)

    def list(self, *, all: bool) -> list[FakeContainer]:
        assert all is True
        return [self.container]

    def get(self, name: str) -> FakeContainer:
        assert name == "plex"
        return self.container


class FakeClient:
    containers = FakeContainers()


class DeniedError(Exception):
    status_code = 403


def test_docker_tools_register_expected_names() -> None:
    registry = ToolRegistry()
    docker_tool.register_tools(registry)

    assert {tool.name for tool in registry.list()} == {
        "docker_list_containers",
        "docker_inspect_container",
        "docker_read_logs",
        "docker_detect_restart_loops",
        "docker_container_action",
    }


def test_container_summary_includes_required_fields() -> None:
    summary = docker_tool._container_summary(FakeContainer(restart_count=2))

    assert summary.id == "abcdef123456"
    assert summary.name == "plex"
    assert summary.image == "sha256:abc123"
    assert summary.health == "healthy"
    assert summary.labels == {"app": "plex"}
    assert summary.ports[0].public_port == 32400
    assert summary.restart_count == 2


def test_log_reads_are_bounded(monkeypatch) -> None:
    monkeypatch.setattr(docker_tool, "_docker_client", lambda: FakeClient())

    result = docker_tool.read_logs(DockerReadLogsArgs(container="plex", lines=2, max_bytes=10))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["truncated"] is True
    assert len(result.data["logs"].encode()) <= 10


def test_restart_loop_detection_uses_restart_count(monkeypatch) -> None:
    monkeypatch.setattr(docker_tool, "_docker_client", lambda: FakeClient())

    result = docker_tool.detect_restart_loops(DockerRestartLoopArgs(min_restarts=3))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["restart_loop_candidates"][0]["name"] == "plex"


def test_socket_proxy_403_returns_permission_error() -> None:
    result = docker_tool._docker_error_result(DeniedError("403 forbidden"))

    assert result.success is False
    assert "denied" in str(result.error)
