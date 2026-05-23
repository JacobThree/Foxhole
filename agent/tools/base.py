from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ToolSafety(StrEnum):
    READ_ONLY = "read_only"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    AUTONOMOUS_ALLOWED = "autonomous_allowed"


class ToolOutputMode(StrEnum):
    SUMMARY = "summary"
    DIAGNOSTIC = "diagnostic"
    RAW = "raw"
    FORENSIC = "forensic"


class WriteActionMetadata(BaseModel):
    requested: bool = False
    safety: ToolSafety = ToolSafety.READ_ONLY
    confirmation_required: bool = False
    confirmation_token: str | None = None
    audit_id: str | None = None


class ToolResult(BaseModel):
    success: bool
    data: dict[str, Any] | list[Any] | str | int | float | bool | None = None
    error: str | None = None
    duration_ms: float = Field(default=0, ge=0)
    output_mode: ToolOutputMode = ToolOutputMode.SUMMARY
    raw_data_withheld: bool = False
    raw_line_count: int | None = Field(default=None, ge=0)
    raw_bytes: int | None = Field(default=None, ge=0)
    write_action: WriteActionMetadata = Field(default_factory=WriteActionMetadata)


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    safety: ToolSafety = ToolSafety.READ_ONLY
    integration: str | None = None
    capability_ids: list[str] = Field(default_factory=list)
    category: str = "read"

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
