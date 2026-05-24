# Foxhole

Foxhole is an open-source, modular, read-only-first homelab diagnostic agent for self-hosters.

It collects compact evidence from the services you already run, explains what looks wrong, and keeps write actions behind explicit safety gates. Every service integration is opt-in: if you do not enable it, Foxhole does not register its tools or spend LLM context on it.

## Architecture And Status

Foxhole is early software. The default runtime is intentionally small: one FastAPI process serves the statically exported Next.js dashboard, REST API, authenticated browser session flow, in-process scheduled diagnostics, in-memory live events, and SQLite-backed history.

```text
Browser -> FastAPI on :8000 -> dashboard, API, scheduler, events, SQLite history
```

The Docker image serves the dashboard from `/app/ui/out`. Source-based LXC and systemd installs serve the same static export from `/opt/homelab-agent/ui/out` through `FOXHOLE_STATIC_UI_DIR`.

Redis, Celery, and Flower are not part of the default runtime. They remain available through a separate distributed Compose file for advanced installs that intentionally want separate API, worker, and beat processes.

## What Foxhole Can Inspect

| Area | Supported Integrations |
| --- | --- |
| Virtualization and storage | Proxmox VE, Proxmox backup job visibility |
| Containers | Docker through a read-only socket proxy, Portainer |
| Media automation | Plex, Sonarr, Radarr, Tautulli, Overseerr |
| Monitoring | Uptime Kuma |
| DNS and network | Pi-hole, Unbound, allowed-subnet LAN discovery |
| Reverse proxy | Caddy route and upstream diagnostics |
| Security posture | Docker and Proxmox read-only risk checks |

## Safety Model

| Stage | Mode | Behavior |
| --- | --- | --- |
| Stage 1 | Read-only default | Inspects logs, queues, containers, DNS, storage, and monitor state. Write-class tools are denied. |
| Stage 2 | Confirmed writes | Narrow write tools require an explicit confirmation token before execution. |
| Stage 3 | Policy-gated automation | Disabled by default. Reserved for narrow remediation loops only. |

The default path is Stage 1. Diagnostics should never mutate homelab state.

## Quick Start: Docker Compose

The standard Compose stack pulls the production image from GHCR:

```text
ghcr.io/jacobthree/foxhole:latest
```

### 1. Initialize Paths And Environment

```bash
mkdir -p iac/compose/data iac/compose/config
cp iac/compose/.env.example iac/compose/config/foxhole.env
```

### 2. Configure Minimum Settings

Edit `iac/compose/config/foxhole.env`:

```env
FOXHOLE_API_BEARER_TOKEN=change-me
FOXHOLE_RUNTIME_MODE=single
FOXHOLE_SCHEDULER_ENABLED=true
FOXHOLE_SESSION_COOKIE_SECURE=false
```

Keep `FOXHOLE_SESSION_COOKIE_SECURE=false` for the default local HTTP URL. Set it to `true` when serving Foxhole behind HTTPS.

### 3. Start Foxhole

```bash
docker compose -f iac/compose/docker-compose.yml up -d
```

Open the dashboard:

```text
http://127.0.0.1:8000
```

Health checks:

```bash
curl http://127.0.0.1:8000/healthz
curl -H "Authorization: Bearer $FOXHOLE_API_BEARER_TOKEN" \
  http://127.0.0.1:8000/readyz
```

## Optional Profiles And Configuration

### Docker Diagnostics

Docker diagnostics require the optional internal socket proxy. Start Compose with the `docker` profile:

```bash
docker compose -f iac/compose/docker-compose.yml --profile docker up -d
```

Then set these values in `iac/compose/config/foxhole.env` or through Settings > Integrations:

```env
FOXHOLE_DOCKER_ENABLED=true
FOXHOLE_DOCKER_SOCKET_PROXY_URL=tcp://docker-socket-proxy:2375
```

The app has no default socket proxy URL. Docker remains incomplete until both the profile is running and the proxy URL is configured.

### LLM Configuration

```env
FOXHOLE_LLM_PRIMARY_MODEL=agent-primary
FOXHOLE_LLM_PRIMARY_API_KEY=
FOXHOLE_LLM_PRIMARY_API_BASE=

FOXHOLE_LLM_LOCAL_MODEL=agent-local
FOXHOLE_LLM_LOCAL_API_BASE=http://host.docker.internal:11434
```

### Distributed Mode

Use distributed mode only when you intentionally want Redis/Celery processes instead of the lightweight single-process runtime:

```bash
docker compose -f iac/compose/docker-compose.distributed.yml up -d
```

Start Flower only when debugging distributed-mode Celery:

```bash
docker compose -f iac/compose/docker-compose.distributed.yml --profile debug up flower
```

### Local Image Builds

Contributors can build the same production image locally and point Compose at it:

```bash
docker build -t foxhole:local .
FOXHOLE_IMAGE=foxhole FOXHOLE_IMAGE_TAG=local docker compose -f iac/compose/docker-compose.yml up -d
```

## Data Persistence And Backups

> Critical state lives in the database path and the editable settings file. Back up both before recreating, moving, or upgrading an install.

| Install Type | Database And History | Settings And Secrets |
| --- | --- | --- |
| Docker Compose | `iac/compose/data/foxhole.db` | `iac/compose/config/foxhole.env` |
| LXC or systemd | `/opt/homelab-agent/data/` | `/etc/homelab-agent/foxhole.env` |

The database stores events, audits, generated incidents, scheduled check results, and history. The env file stores bearer tokens, integration credentials, cookie settings, and dashboard/API-edited settings.

Stop-copy-restore commands are documented in:

- [Docker Compose deployment](docs/deployment/docker-compose.md)
- [Debian and Ubuntu deployment](docs/deployment/debian-ubuntu.md)
- [Proxmox LXC deployment](docs/deployment/proxmox-lxc.md)

## Security Architecture

- **Single exposed app:** Proxy only the unified Foxhole app port, for example Caddy `reverse_proxy 127.0.0.1:8000`.
- **Docker socket boundary:** Compose uses `tecnativa/docker-socket-proxy` only when Docker diagnostics are enabled. Stage 1 exposes read-only Docker API groups and keeps `POST=0`.
- **Secret redaction:** API keys and tokens are Pydantic secrets and are redacted from readiness/config summaries.
- **Scoped tools:** Integrations register tools only after their required configuration is present.
- **LLM context control:** Tools return compact structured evidence by default. Raw logs require explicit bounded output modes.
- **Capability metadata:** Built-in integrations expose manifests through `/integration-manifests` for capability views and future MCP adapter work.

Do not expose the Docker socket proxy, Redis, Celery, or Flower services through a reverse proxy.

## API And Widget Reference

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/healthz` | `GET` | Public process/container health |
| `/readyz` | `GET` | Authenticated readiness and redacted settings summary |
| `/auth/login` | `POST` | Validates bearer token and sets an HTTP-only session cookie |
| `/chat` | `POST` | Evidence-backed agent chat |
| `/events` | `GET` | Recent events |
| `/dashboard/summary` | `GET` | Dashboard control-plane summary |
| `/capabilities` | `GET` | Integration capability view |
| `/integration-manifests` | `GET` | Built-in integration manifests |
| `/widgets/homepage` | `GET` | Optional Homepage/Homarr-compatible status widget |

### Homepage/Homarr Widget

```env
FOXHOLE_WIDGET_ENABLED=true
FOXHOLE_WIDGET_TOKEN=change-me
```

Then poll:

```text
GET /widgets/homepage?token=change-me
```

See [docs/integrations/homepage-homarr.md](docs/integrations/homepage-homarr.md).

## Dashboard Development

Production serves the statically exported dashboard from FastAPI. Run Next.js separately only while working on frontend code:

```bash
cd ui
pnpm install
NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev
```

Open `http://localhost:3000`. Without `NEXT_PUBLIC_API_URL`, the UI uses same-origin API paths for the production static export.

Build the production static export:

```bash
cd ui
pnpm build
```

## Development

Backend:

```bash
python -m pytest -q
python -m ruff check .
```

UI:

```bash
cd ui
pnpm lint
pnpm build
```

## Documentation

- [Architecture](docs/architecture.md)
- [Docker Compose deployment](docs/deployment/docker-compose.md)
- [Debian and Ubuntu deployment](docs/deployment/debian-ubuntu.md)
- [Proxmox LXC deployment](docs/deployment/proxmox-lxc.md)
- [Proxmox permissions](docs/deployment/proxmox-permissions.md)
- [Caddy integration](docs/integrations/caddy.md)
- [Docker integration](docs/integrations/docker.md)
- [Plex integration](docs/integrations/plex.md)
- [Sonarr/Radarr integration](docs/integrations/sonarr-radarr.md)

## Non-Goals Right Now

- No broad autonomous remediation.
- No direct writable Docker socket access in the default Compose stack.
- No MCP server exposure yet; manifests are groundwork for that future adapter.
