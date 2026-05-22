from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ArrService(StrEnum):
    SONARR = "sonarr"
    RADARR = "radarr"


class ArrQueueArgs(BaseModel):
    service: ArrService
    page_size: int = Field(default=50, ge=1, le=500)


class ArrHealthArgs(BaseModel):
    service: ArrService


class ArrRootFoldersArgs(BaseModel):
    service: ArrService


class ArrDownloadClientsArgs(BaseModel):
    service: ArrService


class ArrQualityProfilesArgs(BaseModel):
    service: ArrService


class ArrImportDiagnosisArgs(BaseModel):
    service: ArrService
    page_size: int = Field(default=50, ge=1, le=500)


class ArrQualityProfileUpdateArgs(BaseModel):
    service: ArrService
    profile_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    upgrade_allowed: bool


class ArrQueueItemActionArgs(BaseModel):
    service: ArrService
    queue_id: int = Field(ge=1)
    remove_from_client: bool = True
    blocklist: bool = True
