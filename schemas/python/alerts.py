from typing import Any

from pydantic import BaseModel, Field


class Alert(BaseModel):
    id: str | None = None
    title: str
    message: str
    severity: str = Field(default="info")
    source: str
    data: dict[str, Any] = Field(default_factory=dict)
