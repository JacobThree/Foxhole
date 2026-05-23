from __future__ import annotations

from pydantic import BaseModel, Field


class CaddyListRoutesArgs(BaseModel):
    include_admin_config: bool = True


class CaddyRouteDiagnosisArgs(BaseModel):
    known_container_names: list[str] = Field(default_factory=list)
