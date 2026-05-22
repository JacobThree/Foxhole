from __future__ import annotations

from pydantic import BaseModel, Field


class PlexSessionsArgs(BaseModel):
    pass


class PlexSession(BaseModel):
    user: str | None = None
    title: str | None = None
    player: str | None = None
    player_address: str | None = None
    decision: str
    transcode_hardware: bool = False
    transcode_video_codec: str | None = None
    transcode_audio_codec: str | None = None
    bandwidth_kbps: float | None = None


class PlexTranscodeStatusArgs(BaseModel):
    pass


class PlexLogAnalysisArgs(BaseModel):
    log_path: str = Field(min_length=1)
    max_bytes: int = Field(default=524_288, ge=1024, le=4_194_304)
    max_findings: int = Field(default=50, ge=1, le=500)


class PlexLogFinding(BaseModel):
    category: str
    severity: str
    line: str


class PlexBufferingDiagnosisArgs(BaseModel):
    pass


class PlexDebugGuidanceArgs(BaseModel):
    log_path: str | None = None
