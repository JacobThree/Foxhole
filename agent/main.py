from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from redis import asyncio as redis_async

from agent import __version__
from agent.auth import require_bearer_token
from agent.orchestrator import AgentOrchestrator, create_orchestrator
from agent.settings import AppSettings, get_settings
from schemas.python.chat import ChatRequest, ChatResponse


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


def get_chat_orchestrator(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> AgentOrchestrator:
    return create_orchestrator(settings)


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


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _: Annotated[None, Depends(require_bearer_token)],
    orchestrator: Annotated[AgentOrchestrator, Depends(get_chat_orchestrator)],
) -> ChatResponse:
    return await orchestrator.chat(request)


class SettingsUpdate(BaseModel):
    updates: dict[str, str | bool | None]


@app.patch("/settings", response_model=dict[str, Any])
async def update_settings_endpoint(
    request: SettingsUpdate,
    _: Annotated[None, Depends(require_bearer_token)],
) -> dict[str, Any]:
    from agent.settings import update_env_file
    env_updates = {}
    for k, v in request.updates.items():
        if v is None:
            env_updates[f"FOXHOLE_{k.upper()}"] = None
        else:
            env_updates[f"FOXHOLE_{k.upper()}"] = str(v).lower() if isinstance(v, bool) else str(v)
            
    update_env_file(env_updates)
    get_settings.cache_clear()
    
    # We must also clear the orchestrator tools cache so the updated settings 
    # dynamically reload the registered tools without restarting the backend process.
    from agent.tools.registry import default_registry, register_builtin_tools
    default_registry._tools.clear()
    import agent.tools.registry as reg
    reg._builtins_registered = False
    register_builtin_tools(default_registry)
    
    return get_settings().redacted_summary()


@app.get("/events", response_model=list[dict[str, Any]])
async def list_events(
    _: Annotated[None, Depends(require_bearer_token)],
    limit: int = 50,
) -> list[dict[str, Any]]:
    from agent.events import get_recent_events
    events = await get_recent_events(limit=limit)
    return [e.model_dump() for e in events]

