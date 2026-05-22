from __future__ import annotations

from pydantic import BaseModel, Field


class PiholeSummaryArgs(BaseModel):
    pass


class PiholeRecentBlockedArgs(BaseModel):
    pass


class PiholeQueriesArgs(BaseModel):
    limit: int = Field(default=50, ge=1, le=1000)


class UnboundStatsArgs(BaseModel):
    pass


class NetworkScanArgs(BaseModel):
    subnet: str = Field(min_length=1)
    detect_services: bool = False


class UnknownDeviceArgs(BaseModel):
    subnet: str = Field(min_length=1)
