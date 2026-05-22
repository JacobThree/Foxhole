from __future__ import annotations

from pydantic import BaseModel, Field


class TautulliHistoryArgs(BaseModel):
    length: int = Field(default=50, ge=1, le=500)


class OverseerrRequestsArgs(BaseModel):
    take: int = Field(default=20, ge=1, le=100)
    filter: str | None = None


class OverseerrFailedRequestsArgs(BaseModel):
    take: int = Field(default=50, ge=1, le=200)


class FaultTimelineArgs(BaseModel):
    tautulli_length: int = Field(default=50, ge=1, le=500)
    overseerr_take: int = Field(default=50, ge=1, le=200)
