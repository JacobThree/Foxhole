# Foxhole

Foxhole is a read-only-first homelab diagnostic agent for self-hosters. It collects compact evidence from the services you already run, explains what looks wrong, and keeps write actions behind explicit safety gates.

The project is built around opt-in integrations: if you do not enable an integration, Foxhole does not register its tools or spend agent context on it.

## Current Status

Foxhole is early software. The backend, worker checks, durable history, authenticated browser session flow, and dashboard UI exist, but there is no published container image or release package yet. The Docker Compose stack builds the API locally from this repository.

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

## Quick Start: Backend Stack

The included Compose stack runs:

- FastAPI backend on `127.0.0.1:8000`
- Celery worker and beat scheduler
- Redis
- Internal read-only Docker socket proxy

Flower is available as an optional debug profile on `127.0.0.1:5555`.

Durable history is written to `iac/compose/data/foxhole.db` on the host. Settings changed through the dashboard or API are written to `iac/compose/config/foxhole.env`. Back up both files if you care about event history, audits, incidents, check results, and integration settings.

```bash
mkdir -p iac/compose/data iac/compose/config
cp iac/compose/.env.example iac/compose/config/foxhole.env
$EDITOR iac/compose/config/foxhole.env
docker compose -f iac/compose/docker-compose.yml up --build
```

Start Flower only when debugging Celery:

```bash
docker compose -f iac/compose/docker-compose.yml --profile debug up flower
```

Minimum required setting:

```env
FOXHOLE_API_BEARER_TOKEN=change-me
```

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

## Dashboard UI

The Next.js UI is currently run separately during development:

```bash
cd ui
pnpm install
pnpm dev
```

Open `http://localhost:3000`. The UI talks to `http://localhost:8000` by default. Use the Settings page to log in with the bearer token, then configure integrations under Settings > Integrations.

The integrations page shows:

- configured, incomplete, and disabled integrations
- stable capability IDs such as `containers.list` and `reverse_proxy.routes.diagnose`
- read-only vs confirmation-gated tool behavior
- generated integration manifest metadata and resource URIs

## Architecture And Security

- **Docker socket:** Foxhole uses `tecnativa/docker-socket-proxy` in Compose. Stage 1 exposes read-only Docker API groups and keeps `POST=0`.
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
- No claim of a published production image until releases are actually published.
- No MCP server exposure yet; manifests are groundwork for that future adapter.
