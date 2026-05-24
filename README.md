# Foxhole

Foxhole is a read-only-first homelab diagnostic agent for self-hosters. It collects compact evidence from the services you already run, explains what looks wrong, and keeps write actions behind explicit safety gates.

The project is built around opt-in integrations: if you do not enable an integration, Foxhole does not register its tools or spend agent context on it.

## Current Status

Foxhole is early software. The default runtime is a single FastAPI process that serves the dashboard, API, in-process scheduled diagnostics, authenticated browser session flow, and SQLite-backed history. Tagged releases publish a production image to `ghcr.io/jacobthree/foxhole`; contributors can still build the same image locally from this repository.

## What Foxhole Can Inspect

| Area | Integrations |
| --- | --- |
| Containers | Docker through a socket proxy, Portainer |
| Virtualization and storage | Proxmox VE, Proxmox backup job visibility |
| Media | Plex, Sonarr, Radarr, Tautulli, Overseerr |
| Monitoring | Uptime Kuma |
| DNS and network | Pi-hole, Unbound, allowed-subnet LAN discovery |
| Reverse proxy | Caddy route and upstream diagnostics |
| Security posture | Docker and Proxmox read-only risk checks |

## Safety Model

| Stage | Mode | Behavior |
| --- | --- | --- |
| Stage 1 | Read-only default | Inspects logs, queues, containers, DNS, storage, and monitor state. Write-class tools are denied. |
| Stage 2 | Confirmed writes | Narrow write tools require an explicit confirmation token before execution. |
| Stage 3 | Policy-gated automation | Disabled by default. Intended for narrow remediation rules only. |

The default path is Stage 1. Worker diagnostics are read-only and should never perform mutations.

## Quick Start: Self-Hosted Stack

The included Compose stack runs the default single-process Foxhole app from the GHCR image:

- Static dashboard and FastAPI backend on `127.0.0.1:8000`
- In-process scheduled diagnostics
- In-memory live events
- SQLite durable history
- Optional internal read-only Docker socket proxy

Redis, Celery worker, Celery beat, and Flower are not part of the default stack. They remain available only through the separate distributed Compose file for advanced installs.

Durable history is written to `iac/compose/data/foxhole.db` on the host. Settings changed through the dashboard or API are written to `iac/compose/config/foxhole.env`. Back up both files if you care about event history, audits, incidents, check results, and integration settings.

```bash
mkdir -p iac/compose/data iac/compose/config
cp iac/compose/.env.example iac/compose/config/foxhole.env
$EDITOR iac/compose/config/foxhole.env
docker compose -f iac/compose/docker-compose.yml up -d
```

Open `http://127.0.0.1:8000` for the dashboard.

Enable Docker diagnostics only when you want Foxhole to inspect local containers:

```bash
docker compose -f iac/compose/docker-compose.yml --profile docker up -d
```

Then set these values in `iac/compose/config/foxhole.env` or through Settings > Integrations:

```env
FOXHOLE_DOCKER_ENABLED=true
FOXHOLE_DOCKER_SOCKET_PROXY_URL=tcp://docker-socket-proxy:2375
```

Use the distributed Compose file only when you intentionally want separate Redis/Celery worker processes:

```bash
docker compose -f iac/compose/docker-compose.distributed.yml up -d
```

Start Flower only when debugging distributed-mode Celery:

```bash
docker compose -f iac/compose/docker-compose.distributed.yml --profile debug up flower
```

For contributor builds, build a local image and point Compose at it:

```bash
docker build -t foxhole:local .
FOXHOLE_IMAGE=foxhole FOXHOLE_IMAGE_TAG=local docker compose -f iac/compose/docker-compose.yml up -d
```

Minimum required setting:

```env
FOXHOLE_API_BEARER_TOKEN=change-me
FOXHOLE_RUNTIME_MODE=single
FOXHOLE_SCHEDULER_ENABLED=true
FOXHOLE_SESSION_COOKIE_SECURE=false
```

Keep `FOXHOLE_SESSION_COOKIE_SECURE=false` for the default local HTTP URL. Set it to `true` when serving Foxhole behind HTTPS.

Optional chat/model settings:

```env
FOXHOLE_LLM_PRIMARY_MODEL=agent-primary
FOXHOLE_LLM_PRIMARY_API_KEY=
FOXHOLE_LLM_PRIMARY_API_BASE=
FOXHOLE_LLM_LOCAL_MODEL=agent-local
FOXHOLE_LLM_LOCAL_API_BASE=http://host.docker.internal:11434
```

Health checks:

```bash
curl http://127.0.0.1:8000/healthz
curl -H "Authorization: Bearer $FOXHOLE_API_BEARER_TOKEN" \
  http://127.0.0.1:8000/readyz
```

Detailed Compose notes live in [docs/deployment/docker-compose.md](docs/deployment/docker-compose.md).

Back up `iac/compose/data/` and `iac/compose/config/` for Compose installs. For LXC or systemd installs, back up `/opt/homelab-agent/data/` and `/etc/homelab-agent/foxhole.env`. The deployment docs include stop-copy-restore commands for each path.

To serve Foxhole behind HTTPS, proxy only the unified app port, for example Caddy `reverse_proxy 127.0.0.1:8000`, and set `FOXHOLE_SESSION_COOKIE_SECURE=true`. Do not expose the Docker socket proxy, Redis, Celery, or Flower services.

## Architecture

Production Foxhole is intentionally small:

```text
Browser -> FastAPI on :8000 -> static dashboard, API, scheduler, SQLite history
```

The Docker image copies the exported Next.js dashboard into `/app/ui/out` and FastAPI serves it directly. LXC and systemd installs serve the same export from `/opt/homelab-agent/ui/out` through `FOXHOLE_STATIC_UI_DIR`. In the default `single` runtime, scheduled checks run inside the app process and live events use an in-memory bus. Redis is only checked in `distributed` mode.

## Dashboard UI

The production dashboard is statically exported into the backend image and served by FastAPI. Run the Next.js UI separately only during frontend development:

```bash
cd ui
pnpm install
NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev
```

Open `http://localhost:3000`. `NEXT_PUBLIC_API_URL` points the dev UI at the backend. Without it, the UI uses same-origin API paths for production. Use the Settings page to log in with the bearer token, then configure integrations under Settings > Integrations.

The integrations page shows:

- configured, incomplete, and disabled integrations
- stable capability IDs such as `containers.list` and `reverse_proxy.routes.diagnose`
- read-only vs confirmation-gated tool behavior
- generated integration manifest metadata and resource URIs

## Architecture And Security

- **Default runtime:** One FastAPI process serves the dashboard, API, scheduler, event stream, and SQLite history.
- **Docker socket:** Foxhole uses `tecnativa/docker-socket-proxy` only when Docker diagnostics are enabled. Stage 1 exposes read-only Docker API groups and keeps `POST=0`.
- **Secrets:** API keys and tokens are represented as Pydantic secrets and redacted from readiness/config summaries.
- **LLM context:** Tools return compact structured evidence by default. Raw logs require explicit bounded output modes.
- **Integrations:** Tools are registered only when their integration is configured, which keeps agent context and permissions scoped to your environment.
- **Manifests:** Built-in integrations expose metadata through `/integration-manifests` for future plugin and MCP adapter work.

## Useful Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /healthz` | Public process health |
| `GET /readyz` | Authenticated readiness and redacted settings summary |
| `POST /auth/login` | Validates bearer token and sets an HTTP-only browser session cookie |
| `POST /chat` | Evidence-backed agent chat |
| `GET /events` | Recent events |
| `GET /dashboard/summary` | Dashboard control-plane summary |
| `GET /capabilities` | Integration capability view |
| `GET /integration-manifests` | Built-in integration manifests |
| `GET /widgets/homepage` | Optional Homepage/Homarr-compatible status widget |

## Homepage/Homarr Widget

The widget endpoint is disabled by default and can be protected with a separate token:

```env
FOXHOLE_WIDGET_ENABLED=true
FOXHOLE_WIDGET_TOKEN=change-me
```

Then poll:

```text
GET /widgets/homepage?token=change-me
```

See [docs/integrations/homepage-homarr.md](docs/integrations/homepage-homarr.md).

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

## Non-Goals Right Now

- No broad autonomous remediation.
- No direct writable Docker socket access in the default Compose stack.
- No MCP server exposure yet; manifests are groundwork for that future adapter.
