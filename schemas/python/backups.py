from __future__ import annotations

from pydantic import BaseModel, Field


class BackupStorageHealthArgs(BaseModel):
    max_used_percent: float = Field(default=85.0, ge=1, le=100)
    stale_after_hours: int = Field(default=36, ge=1, le=24 * 30)
    datastore_thresholds: dict[str, float] = Field(default_factory=dict)
    local_paths: list[str] = Field(default_factory=list, max_length=20)
