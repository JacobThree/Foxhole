from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from redis import asyncio as redis_async

from agent import __version__
from agent.auth import require_bearer_token
from agent.settings import AppSettings, get_settings


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, bool]
    settings: dict[str, Any]


app = FastAPI(
    title="Foxhole",
    version=__version__,
    description="Read-only-first homelab diagnostic agent.",
)


async def check_redis_ready(settings: Annotated[AppSettings, Depends(get_settings)]) -> bool:
    client = redis_async.from_url(  # type: ignore[no-untyped-call]
        settings.redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=True,
    )
    try:
        pong = await client.ping()
    finally:
        await client.aclose()
    return bool(pong)


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service="foxhole", version=__version__)


@app.get("/readyz", response_model=ReadyResponse)
async def readyz(
    _: Annotated[None, Depends(require_bearer_token)],
    redis_ready: Annotated[bool, Depends(check_redis_ready)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> ReadyResponse:
    checks = {
        "settings": settings.api_auth_configured,
        "redis": redis_ready,
    }
    if not all(checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "checks": checks,
                "settings": settings.redacted_summary(),
            },
        )

    return ReadyResponse(
        status="ok",
        checks=checks,
        settings=settings.redacted_summary(),
    )
