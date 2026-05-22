from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class DockerContainerPort(BaseModel):
    private_port: int | None = None
    public_port: int | None = None
    protocol: str | None = None
    ip: str | None = None


class DockerContainerSummary(BaseModel):
    id: str
    name: str
    image: str
    image_tags: list[str] = Field(default_factory=list)
    status: str
    health: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    ports: list[DockerContainerPort] = Field(default_factory=list)
    restart_count: int = 0


class DockerListContainersArgs(BaseModel):
    all: bool = True


class DockerInspectContainerArgs(BaseModel):
    container: str = Field(min_length=1)


class DockerReadLogsArgs(BaseModel):
    container: str = Field(min_length=1)
    lines: int = Field(ge=1, le=1000)
    max_bytes: int = Field(ge=1, le=1_048_576)


class DockerRestartLoopArgs(BaseModel):
    all: bool = True
    min_restarts: int = Field(default=3, ge=1, le=100)


class DockerContainerAction(StrEnum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"


class DockerContainerActionArgs(BaseModel):
    container: str = Field(min_length=1)
    action: DockerContainerAction
    timeout_seconds: int = Field(default=30, ge=1, le=300)
