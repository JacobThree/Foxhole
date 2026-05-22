from __future__ import annotations

from pydantic import BaseModel, SecretStr

from agent.safety import AuditLog, WritePolicy
from agent.settings import AppSettings
from agent.tools.base import ToolResult, ToolSafety
from agent.tools.registry import ToolRegistry
from schemas.python.docker import DockerContainerAction, DockerContainerActionArgs
from tools import docker_tool


class FakeImage:
    short_id = "sha256:abc123"
    tags = ["nginx:latest"]


class FakeContainer:
    id = "abcdef123456"
    name = "web"
    image = FakeImage()
    status = "running"

    def __init__(self) -> None:
        self.actions: list[str] = []
        self.attrs = {"Config": {"Labels": {}}, "State": {"Status": "running", "RestartCount": 0}}

    def restart(self, *, timeout: int) -> None:
        self.actions.append(f"restart:{timeout}")

    def reload(self) -> None:
        self.status = "running"


class FakeContainers:
    def __init__(self, container: FakeContainer) -> None:
        self._container = container

    def get(self, name: str) -> FakeContainer:
        assert name == "web"
        return self._container


class FakeClient:
    def __init__(self, container: FakeContainer) -> None:
        self.containers = FakeContainers(container)


def test_docker_action_requires_confirmation_in_policy() -> None:
    registry = ToolRegistry()
    docker_tool.register_tools(registry)
    tool = registry.get("docker_container_action")
    args = DockerContainerActionArgs(container="web", action=DockerContainerAction.RESTART)
    policy = WritePolicy(
        AppSettings(write_stage=2, write_confirmation_secret=SecretStr("secret")),
    )

    decision = policy.evaluate(tool=tool, caller="test", arguments=args)

    assert tool.safety is ToolSafety.REQUIRES_CONFIRMATION
    assert decision.allowed is False
    assert decision.write_action.confirmation_required is True


def test_confirmed_restart_records_old_and_new_status(monkeypatch) -> None:
    container = FakeContainer()
    monkeypatch.setattr(docker_tool, "_docker_client", lambda: FakeClient(container))

    result = docker_tool.container_action(
        DockerContainerActionArgs(
            container="web",
            action=DockerContainerAction.RESTART,
            timeout_seconds=5,
        )
    )

    assert result.success is True
    assert container.actions == ["restart:5"]
    assert isinstance(result.data, dict)
    assert result.data["old_status"]["status"] == "running"
    assert result.data["resulting_status"]["status"] == "running"


def test_action_schema_refuses_unsupported_operations() -> None:
    registry = ToolRegistry()

    @registry.register(
        name="fake",
        description="fake",
        args_model=DockerContainerActionArgs,
        safety=ToolSafety.REQUIRES_CONFIRMATION,
    )
    def fake(arguments: BaseModel) -> ToolResult:
        return ToolResult(success=True, data=arguments.model_dump())

    schema = registry.get("fake").schema()

    assert set(schema["$defs"]["DockerContainerAction"]["enum"]) == {"start", "stop", "restart"}


def test_audit_log_can_record_action_before_and_after_status() -> None:
    audit_log = AuditLog()
    policy = WritePolicy(
        AppSettings(write_stage=2, write_confirmation_secret=SecretStr("secret")),
        audit_log,
    )
    registry = ToolRegistry()
    docker_tool.register_tools(registry)
    tool = registry.get("docker_container_action")
    args = DockerContainerActionArgs(container="web", action=DockerContainerAction.RESTART)
    token = policy.confirmation_token(tool.name, "test", args.model_dump(mode="json"))

    decision = policy.evaluate(
        tool=tool,
        caller="test",
        arguments=args,
        confirmation_token=token,
    )
    policy.record_tool_result(
        decision.write_action.audit_id,
        {
            "action": "restart",
            "old_status": {"status": "running"},
            "resulting_status": {"status": "running"},
        },
        success=True,
    )

    assert audit_log.events[0].result == "succeeded"
    assert isinstance(audit_log.events[0].result_data, dict)
    assert audit_log.events[0].result_data["action"] == "restart"
    assert audit_log.events[0].result_data["old_status"]["status"] == "running"
    assert audit_log.events[0].result_data["resulting_status"]["status"] == "running"
