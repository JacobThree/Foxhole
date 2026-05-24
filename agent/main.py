from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from redis import asyncio as redis_async

from agent import __version__
from agent.auth import (
    AuthSessionResponse,
    login_with_bearer_token,
    logout_session,
    require_bearer_token,
)
from agent.orchestrator import AgentOrchestrator, create_orchestrator
from agent.scheduler import create_scheduler
from agent.settings import AppSettings, get_settings
from schemas.python.chat import ChatRequest, ChatResponse
from schemas.python.events import (
    AuditReceipt,
    DashboardSummary,
    DashboardWidgetSummary,
    IncidentDetail,
    IncidentSummary,
    IntegrationCapabilities,
    IntegrationManifest,
    IntegrationState,
)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, bool]
    settings: dict[str, Any]


STATIC_UI_DIR = Path(__file__).resolve().parent.parent / "ui" / "out"


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    scheduler = create_scheduler(get_settings())
    fastapi_app.state.scheduler = scheduler
    if scheduler is not None:
        await scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()


app = FastAPI(
    title="Foxhole",
    version=__version__,
    description="Read-only-first homelab diagnostic agent.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().ui_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def check_redis_ready(settings: Annotated[AppSettings, Depends(get_settings)]) -> bool:
    if settings.runtime_mode == "single":
        return True

    client = redis_async.from_url(  # type: ignore[no-untyped-call]
        settings.redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=True,
    )
    try:
        pong = await client.ping()
    finally:
        await client.close()
    return bool(pong)


def get_chat_orchestrator(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> AgentOrchestrator:
    return create_orchestrator(settings)


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service="foxhole", version=__version__)


@app.post("/auth/login", response_model=AuthSessionResponse)
async def auth_login(
    session: Annotated[AuthSessionResponse, Depends(login_with_bearer_token)],
) -> AuthSessionResponse:
    return session


@app.post("/auth/logout", response_model=AuthSessionResponse)
async def auth_logout(
    session: Annotated[AuthSessionResponse, Depends(logout_session)],
) -> AuthSessionResponse:
    return session


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
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> dict[str, Any]:
    from agent.settings import update_env_file

    env_updates: dict[str, str | None] = {}
    for k, v in request.updates.items():
        if v is None:
            env_updates[f"FOXHOLE_{k.upper()}"] = None
        else:
            env_updates[f"FOXHOLE_{k.upper()}"] = str(v).lower() if isinstance(v, bool) else str(v)

    update_env_file(env_updates, settings=settings)
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


@app.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    _: Annotated[None, Depends(require_bearer_token)],
    redis_ready: Annotated[bool, Depends(check_redis_ready)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    limit: int = 50,
) -> DashboardSummary:
    from agent.events import get_recent_events, latest_check_summaries, severity_counts

    event_limit = min(max(limit, 1), 200)
    events = await get_recent_events(limit=event_limit)
    integration_details = settings.integration_details()
    return DashboardSummary(
        readiness={
            "settings": settings.api_auth_configured,
            "redis": redis_ready,
        },
        integrations=[
            IntegrationState(name=name, **detail)
            for name, detail in integration_details.items()
        ],
        severity_counts=severity_counts(events),
        latest_checks=latest_check_summaries(events),
        recent_events=[
            event
            for event in events
            if event.severity.lower() in {"critical", "error", "high", "warning", "warn"}
        ][:5],
    )


@app.get("/widgets/homepage", response_model=DashboardWidgetSummary)
async def homepage_widget(
    request: Request,
    settings: Annotated[AppSettings, Depends(get_settings)],
    limit: int = 50,
) -> DashboardWidgetSummary:
    if not settings.widget_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget is disabled")
    _require_widget_token(request, settings)

    from agent.db.repositories import IncidentRepository
    from agent.events import get_recent_events, severity_counts

    events = await get_recent_events(limit=min(max(limit, 1), 200))
    counts = severity_counts(events)
    warning_count = counts.get("warning", 0)
    critical_count = counts.get("critical", 0)
    widget_status = "critical" if critical_count else "warning" if warning_count else "ok"
    latest_incidents = IncidentRepository(settings).list_generated(limit=1)
    latest_event = next(
        (
            event
            for event in events
            if event.severity.lower() in {"critical", "error", "high", "warning", "warn"}
        ),
        None,
    )
    return DashboardWidgetSummary(
        status=widget_status,
        warning_count=warning_count,
        critical_count=critical_count,
        latest_incident=latest_incidents[0] if latest_incidents else None,
        suggested_action=_widget_suggested_action(latest_event),
    )


def _require_widget_token(request: Request, settings: AppSettings) -> None:
    if settings.widget_token is None:
        return
    expected = settings.widget_token.get_secret_value()
    provided = request.query_params.get("token") or request.headers.get("x-foxhole-widget-token")
    if not provided:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            provided = auth_header[7:]
    if provided != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid widget token")


def _widget_suggested_action(event: Any | None) -> str | None:
    if event is None:
        return None
    if event.findings:
        for finding in event.findings:
            if finding.suggested_actions:
                return str(finding.suggested_actions[0].description)
    summary = event.payload_summary
    return str(summary) if summary else "Review the latest Foxhole event."


@app.get("/capabilities", response_model=list[IntegrationCapabilities])
async def list_capabilities(
    _: Annotated[None, Depends(require_bearer_token)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> list[IntegrationCapabilities]:
    from agent.tools.registry import ToolRegistry, integration_capabilities, register_builtin_tools

    registry = ToolRegistry()
    register_builtin_tools(registry, settings=settings)
    return integration_capabilities(settings, registry)


@app.get("/integration-manifests", response_model=list[IntegrationManifest])
async def list_integration_manifests(
    _: Annotated[None, Depends(require_bearer_token)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> list[IntegrationManifest]:
    from agent.tools.registry import ToolRegistry, integration_manifests, register_builtin_tools

    registry = ToolRegistry()
    register_builtin_tools(registry, settings=settings)
    return integration_manifests(settings, registry)


@app.get("/audits", response_model=list[AuditReceipt])
async def list_audits(
    _: Annotated[None, Depends(require_bearer_token)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    limit: int = 50,
) -> list[AuditReceipt]:
    from agent.db.repositories import AuditRepository

    return AuditRepository(settings).recent(limit=limit)


@app.get("/incidents", response_model=list[IncidentSummary])
async def list_incidents(
    _: Annotated[None, Depends(require_bearer_token)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    limit: int = 50,
) -> list[IncidentSummary]:
    from agent.db.repositories import IncidentRepository

    return IncidentRepository(settings).list_generated(limit=limit)


@app.get("/incidents/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: str,
    _: Annotated[None, Depends(require_bearer_token)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> IncidentDetail:
    from agent.db.repositories import IncidentRepository

    incident = IncidentRepository(settings).detail(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


def _static_ui_file(full_path: str) -> Path | None:
    if not STATIC_UI_DIR.is_dir():
        return None

    requested = full_path.strip("/")
    if ".." in Path(requested).parts:
        return None

    candidates: list[Path] = []
    if requested == "":
        candidates.append(STATIC_UI_DIR / "index.html")
    else:
        raw_path = STATIC_UI_DIR / requested
        candidates.extend(
            [
                raw_path,
                raw_path / "index.html",
                STATIC_UI_DIR / f"{requested}.html",
            ]
        )

    for candidate in candidates:
        try:
            candidate.relative_to(STATIC_UI_DIR)
        except ValueError:
            continue
        if candidate.is_file():
            return candidate

    if requested.startswith("_next/") or Path(requested).suffix:
        return None

    fallback = STATIC_UI_DIR / "index.html"
    return fallback if fallback.is_file() else None


@app.get("/", include_in_schema=False)
async def serve_static_ui_root() -> FileResponse:
    static_file = _static_ui_file("")
    if static_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not built")
    return FileResponse(static_file)


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_static_ui(full_path: str) -> FileResponse:
    static_file = _static_ui_file(full_path)
    if static_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return FileResponse(static_file)
