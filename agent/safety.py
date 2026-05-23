from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from agent.db.repositories import AuditRepository
from agent.settings import AppSettings
from agent.tools.base import ToolSafety, WriteActionMetadata
from agent.tools.registry import RegisteredTool
from schemas.python.events import AuditReceipt, get_utc_now


class AuditEvent(BaseModel):
    id: str
    timestamp: str = Field(default_factory=get_utc_now)
    tool_name: str
    caller: str
    arguments: dict[str, Any]
    safety: ToolSafety
    confirmation_status: str
    result: str
    result_data: dict[str, Any] | list[Any] | str | int | float | bool | None = None


@dataclass
class AuditLog:
    events: list[AuditEvent] = field(default_factory=list)

    def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    def update_result(
        self,
        audit_id: str,
        *,
        result: str,
        result_data: dict[str, Any] | list[Any] | str | int | float | bool | None = None,
    ) -> None:
        for event in self.events:
            if event.id == audit_id:
                event.result = result
                event.result_data = result_data
                return


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str | None = None
    write_action: WriteActionMetadata = Field(default_factory=WriteActionMetadata)


class WritePolicy:
    def __init__(
        self,
        settings: AppSettings,
        audit_log: AuditLog | None = None,
        audit_repository: AuditRepository | None = None,
    ) -> None:
        self._settings = settings
        self._audit_log = audit_log or AuditLog()
        self._audit_repository: AuditRepository | None = (
            audit_repository if audit_repository is not None else AuditRepository(settings)
        )
        if audit_log is not None and audit_repository is None:
            self._audit_repository = None

    @property
    def audit_log(self) -> AuditLog:
        return self._audit_log

    def evaluate(
        self,
        *,
        tool: RegisteredTool,
        caller: str,
        arguments: BaseModel,
        confirmation_token: str | None = None,
    ) -> PolicyDecision:
        if tool.safety is ToolSafety.READ_ONLY:
            return PolicyDecision(allowed=True)

        args = arguments.model_dump(mode="json")
        audit_id = str(uuid.uuid4())
        expected_token = self.confirmation_token(tool.name, caller, args)
        metadata = WriteActionMetadata(
            requested=True,
            safety=tool.safety,
            confirmation_required=True,
            confirmation_token=expected_token,
            audit_id=audit_id,
        )

        if self._settings.write_stage <= 1:
            self._record(audit_id, tool, caller, args, "denied_stage_1", "denied")
            return PolicyDecision(
                allowed=False,
                reason="Write actions are disabled in stage 1.",
                write_action=metadata,
            )

        confirmed = confirmation_token == expected_token
        needs_confirmation = (
            tool.safety is ToolSafety.REQUIRES_CONFIRMATION or self._settings.write_stage == 2
        )
        if needs_confirmation and not confirmed:
            self._record(audit_id, tool, caller, args, "confirmation_required", "blocked")
            return PolicyDecision(
                allowed=False,
                reason="Write action requires confirmation.",
                write_action=metadata,
            )

        self._record(
            audit_id,
            tool,
            caller,
            args,
            "confirmed" if confirmed else "autonomous",
            "allowed",
        )
        metadata.confirmation_required = False
        metadata.confirmation_token = None
        return PolicyDecision(allowed=True, write_action=metadata)

    def record_tool_result(self, audit_id: str | None, result_data: Any, success: bool) -> None:
        if audit_id is None:
            return
        self._audit_log.update_result(
            audit_id,
            result="succeeded" if success else "failed",
            result_data=_redact_sensitive(result_data),
        )
        if self._audit_repository is not None:
            self._audit_repository.update_result(
                audit_id,
                result="succeeded" if success else "failed",
                result_data=_redact_sensitive(result_data),
            )

    def confirmation_token(self, tool_name: str, caller: str, arguments: dict[str, Any]) -> str:
        secret = (
            self._settings.write_confirmation_secret.get_secret_value()
            if self._settings.write_confirmation_secret is not None
            else "development-confirmation-secret"
        )
        payload = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(f"{secret}:{tool_name}:{caller}:{payload}".encode()).hexdigest()
        return digest[:20]

    def _record(
        self,
        audit_id: str,
        tool: RegisteredTool,
        caller: str,
        arguments: dict[str, Any],
        confirmation_status: str,
        result: str,
    ) -> None:
        self._audit_log.append(
            event := AuditEvent(
                id=audit_id,
                tool_name=tool.name,
                caller=caller,
                arguments=_redact_sensitive(arguments),
                safety=tool.safety,
                confirmation_status=confirmation_status,
                result=result,
            )
        )
        if self._audit_repository is not None:
            self._audit_repository.create(
                AuditReceipt(
                    id=event.id,
                    timestamp=event.timestamp,
                    tool_name=event.tool_name,
                    caller=event.caller,
                    arguments=event.arguments,
                    safety=event.safety.value,
                    confirmation_status=event.confirmation_status,
                    result=event.result,
                    result_data=event.result_data,
                )
            )


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if any(marker in normalized for marker in ("token", "secret", "password", "api_key")):
                redacted[str(key)] = "********"
            else:
                redacted[str(key)] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value
