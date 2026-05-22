from __future__ import annotations

from pydantic import BaseModel, Field


class PortainerListEndpointsArgs(BaseModel):
    pass


class PortainerListStacksArgs(BaseModel):
    endpoint_id: int | None = Field(default=None, ge=1)


class PortainerStackDetailsArgs(BaseModel):
    stack_id: int = Field(ge=1)
    endpoint_id: int | None = Field(default=None, ge=1)


class PortainerRedeployStackArgs(BaseModel):
    stack_id: int = Field(ge=1)
    endpoint_id: int = Field(ge=1)
    pull_image: bool = True
    prune: bool = False
