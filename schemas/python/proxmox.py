from __future__ import annotations

from pydantic import BaseModel, Field


class ProxmoxNodeStatusArgs(BaseModel):
    node: str | None = Field(default=None, min_length=1)


class ProxmoxInventoryArgs(BaseModel):
    node: str | None = Field(default=None, min_length=1)
    include_vms: bool = True
    include_lxcs: bool = True


class ProxmoxStorageArgs(BaseModel):
    node: str | None = Field(default=None, min_length=1)


class ProxmoxBackupJobsArgs(BaseModel):
    pass


class ProxmoxMigrateLxcArgs(BaseModel):
    vmid: int = Field(ge=1)
    source_node: str = Field(min_length=1)
    target_node: str = Field(min_length=1)
    online: bool = True
