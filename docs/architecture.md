# Architecture

Foxhole's default architecture is a single-process homelab agent. One FastAPI
process serves the dashboard, API, authenticated settings flow, in-process
scheduler, event stream, and SQLite-backed history.

This is the default because Foxhole is single-tenant self-hosted software. Most
installs should not need Redis, Celery, a separate UI server, or internal service
networking beyond the optional Docker socket proxy.

## Default Runtime

```text
Browser
  |
  | HTTP on 127.0.0.1:8000 or reverse proxy
  v
FastAPI process
  |-- static dashboard from ui/out
  |-- REST API and auth/session cookies
  |-- in-process scheduled diagnostics
  |-- in-memory live event bus
  |-- SQLite durable history
  |-- opt-in integration tools
```

The production dashboard is a static Next.js export. In Docker images it is
copied to `/app/ui/out`; source-based systemd and LXC installs serve it from
`/opt/homelab-agent/ui/out` through `FOXHOLE_STATIC_UI_DIR`.

## Components

| Component | Default Role |
| --- | --- |
| `agent` | FastAPI app, auth, settings, orchestration, scheduler, static dashboard serving |
| `tools` | Read-only integrations for Docker, Proxmox, media services, DNS, network, reverse proxy, and monitoring |
| `workers` | Shared scheduled-check functions plus optional Celery wrappers for distributed mode |
| `schemas` | Typed contracts used by API responses, tools, scheduled checks, and UI clients |
| `ui` | Next.js dashboard, statically exported for production |
| `iac` | Compose, LXC, systemd, and Ansible deployment assets |

## Scheduling And Events

In `FOXHOLE_RUNTIME_MODE=single`, scheduled checks run inside the FastAPI
lifecycle. Each check has an overlap guard; if a previous run is still active,
the next run is skipped. Durable events and check results are written to SQLite,
and live updates use an in-memory event bus.

Redis is not required in single-process mode. `/readyz` reports Redis healthy in
that mode because there is no Redis dependency to check.

## Optional Distributed Runtime

`iac/compose/docker-compose.distributed.yml` keeps the Redis/Celery shape
available for advanced installs that intentionally want separate API, worker,
and beat processes.

Use distributed mode only when you have a reason to operate those extra services:

| Concern | Single-Process Default | Distributed Mode |
| --- | --- | --- |
| Dashboard/API | FastAPI | FastAPI |
| Scheduled checks | In-process scheduler | Celery beat and worker |
| Live events | In-memory bus | Redis-backed event flow |
| Durable history | SQLite | SQLite |
| Containers | 1, plus optional socket proxy | API, Redis, worker, beat, plus optional socket proxy |

Distributed mode sets `FOXHOLE_RUNTIME_MODE=distributed` and requires
`FOXHOLE_REDIS_URL`. It is not the recommended first install path.

## Configuration And Opt-In Integrations

Settings are loaded through Pydantic from `FOXHOLE_*` environment variables and
the configured env file. Compose stores editable settings in
`iac/compose/config/foxhole.env`; systemd and LXC installs use
`/etc/homelab-agent/foxhole.env`.

Integrations are disabled by default. Enabling an integration is not enough by
itself; required connection details must also be present before tools are
registered. For example, Docker diagnostics require both:

```env
FOXHOLE_DOCKER_ENABLED=true
FOXHOLE_DOCKER_SOCKET_PROXY_URL=tcp://docker-socket-proxy:2375
```

The dashboard writes settings through `PATCH /settings`, then clears settings
and tool-registry caches so capability changes are visible without a restart.
Secrets are represented as Pydantic secrets and redacted from readiness,
configuration summaries, logs, and support output.

## Docker Boundary

Foxhole does not mount a writable Docker socket into the app. Compose uses
`tecnativa/docker-socket-proxy` behind the optional `docker` profile. Stage 1
exposes read-only Docker API groups and keeps `POST=0`.

The socket proxy is not part of the default one-container environment. This
keeps a fresh install lean and prevents Docker tools from appearing configured
until the user intentionally starts the proxy and supplies its internal URL.

## Read-Only First

Stage 1 diagnostics collect logs, metadata, queue state, health state, and
storage signals. Write-class tools are denied.

Stage 2 write tools must declare themselves as write-capable, pass the shared
write policy, require explicit confirmation, and emit audit records. Stage 3
autonomous remediation is disabled by default and should remain narrow and
policy-gated.

## Capability And Manifest Metadata

Every registered tool exposes stable capability IDs such as `containers.list`,
`media.arr.queue.read`, `monitoring.monitors.read`, and
`reverse_proxy.routes.diagnose`. The registry also records each tool's owning
integration and read/write category.

Built-in integrations expose manifest metadata through `/integration-manifests`.
Each manifest includes config requirements, exposed capabilities, tool schemas,
safety levels, resource URIs, event types, diagnostic bundles, and future MCP
adapter notes.

Manifests describe existing integrations. They do not grant extra permissions or
change runtime safety behavior.

## API Foundation

The API exposes public process health at `/healthz` and authenticated readiness
at `/readyz`. The dashboard and API are same-origin in production, so reverse
proxies should route only the unified Foxhole app port.
