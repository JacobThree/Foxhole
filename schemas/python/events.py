import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def get_utc_now() -> str:
    return datetime.now(UTC).isoformat()


def generate_id() -> str:
    return str(uuid.uuid4())


class Event(BaseModel):
    id: str = Field(default_factory=generate_id)
    timestamp: str = Field(default_factory=get_utc_now)
    type: str  # "alert", "tool_call", "confirmation", "write_result"
    severity: str = "info"
    source: str
    payload_summary: str
    correlation_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
