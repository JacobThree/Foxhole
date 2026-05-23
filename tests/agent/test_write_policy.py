import pytest
from pydantic import BaseModel, SecretStr

from agent.db.repositories import AuditRepository
from agent.safety import AuditLog, WritePolicy
from agent.settings import AppSettings
from agent.tools.base import ToolResult, ToolSafety
from agent.tools.registry import ToolRegistry


class RestartArgs(BaseModel):
    container: str


@pytest.fixture
def isolated_database(tmp_path, monkeypatch: pytest.MonkeyPatch) -> str:
    path = str(tmp_path / "foxhole.db")
    monkeypatch.setenv("FOXHOLE_DATABASE_PATH", path)
    return path


def _restart_tool():
    registry = ToolRegistry()

    @registry.register(
        name="restart_container",
        description="Restart a container.",
        args_model=RestartArgs,
        safety=ToolSafety.REQUIRES_CONFIRMATION,
    )
    def restart(arguments: BaseModel) -> ToolResult:
        return ToolResult(success=True, data=arguments.model_dump())

    return registry.get("restart_container")


def test_stage_1_denies_write_actions_and_records_audit() -> None:
    audit_log = AuditLog()
    policy = WritePolicy(AppSettings(write_stage=1), audit_log)

    decision = policy.evaluate(
        tool=_restart_tool(),
        caller="test",
        arguments=RestartArgs(container="plex"),
    )

    assert decision.allowed is False
    assert decision.write_action.confirmation_required is True
    assert audit_log.events[0].confirmation_status == "denied_stage_1"


def test_stage_2_requires_confirmation_token() -> None:
    settings = AppSettings(
        write_stage=2,
        write_confirmation_secret=SecretStr("confirm-secret"),
    )
    policy = WritePolicy(settings)
    tool = _restart_tool()
    args = RestartArgs(container="plex")
    token = policy.confirmation_token(tool.name, "test", args.model_dump(mode="json"))

    blocked = policy.evaluate(tool=tool, caller="test", arguments=args)
    allowed = policy.evaluate(tool=tool, caller="test", arguments=args, confirmation_token=token)

    assert blocked.allowed is False
    assert blocked.write_action.confirmation_token == token
    assert allowed.allowed is True


def test_write_policy_persists_durable_audit_receipts(isolated_database: str) -> None:
    settings = AppSettings(
        write_stage=1,
        database_path=isolated_database,
    )
    policy = WritePolicy(settings)

    decision = policy.evaluate(
        tool=_restart_tool(),
        caller="test",
        arguments=RestartArgs(container="plex"),
    )

    receipts = AuditRepository(settings).recent()
    assert decision.allowed is False
    assert receipts[0].tool_name == "restart_container"
    assert receipts[0].confirmation_status == "denied_stage_1"
    assert receipts[0].arguments == {"container": "plex"}
