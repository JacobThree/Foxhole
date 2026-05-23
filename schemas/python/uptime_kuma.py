from __future__ import annotations

from pydantic import BaseModel, Field


class UptimeKumaMonitorStatusArgs(BaseModel):
    include_paused: bool = True


class UptimeKumaRecentFailuresArgs(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
