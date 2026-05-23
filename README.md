# Foxhole

Foxhole is a read-only-first homelab diagnostic agent for self-hosters. It is designed to inspect common services such as Proxmox, Docker, Plex, Sonarr, Radarr, Tautulli, Overseerr, Pi-hole, Unbound, and local network devices, then explain what it sees through an API that can later power chat, alerts, and a web UI.

The first milestone is intentionally conservative: collect diagnostics, expose health and readiness checks, and prepare for Telegram alerts without restarting containers, changing media server settings, migrating LXCs, or editing network configuration. Write actions will be added later behind explicit human confirmation and audit logging.

## Current Status

Phase 4 builds infrastructure diagnostics:

- Python package scaffold for the agent, tools, workers, schemas, deployment artifacts, and docs.
- Pydantic settings with redacted secret output.
- FastAPI shell with health, readiness, and bearer-token protection.
- Test, lint, and type-check commands for contributors.
- LiteLLM provider aliases for `agent-primary`, `agent-local`, and `agent-vllm`.
- Typed tool registration with OpenAI-compatible JSON schema export.
- Strict tool argument parsing with bounded correction hooks for fake or real LLM clients.
- Authenticated `/chat` orchestration through the tool registry.
- Write-action policy that denies writes in stage 1 and requires confirmation tokens in stage 2.
- Docker Compose deployment for API, worker, beat, Redis, Flower, and a read-only Docker socket proxy.
- Proxmox API token helper and LXC bootstrap path.
- Debian/Ubuntu Ansible install path and GitHub Actions CI/container build.
- Docker container status, bounded logs, image metadata, restart-loop diagnostics, and confirmed start/stop/restart actions.
- Portainer endpoint and stack diagnostics with API-token auth and confirmed Git redeploy.
- Proxmox node, inventory, storage, backup job, and confirmed LXC migration tools.
- Backup and storage health summary for stale jobs, failed jobs, full datastores, and local filesystem usage.

## First Local Install Path

Create a virtual environment, install the package with development dependencies, then run the checks:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
ruff check .
mypy agent tools workers
```

Copy `.env.example` to `.env`, fill in at least `FOXHOLE_API_BEARER_TOKEN`, and start the API:

```bash
uvicorn agent.main:app --reload
```

Open `http://127.0.0.1:8000/healthz` for process health. Use `/readyz` to verify settings and Redis availability.

Phase 2 chat uses the configured LiteLLM alias `agent-primary` by default, with `agent-local` and `agent-vllm` documented as fallback targets. Tests use fake LLM clients, so the runtime can be developed without live model credentials.

## Mock Mode (No-Homelab Demo)

To run the UI and backend locally without connecting to real Proxmox, Docker, or Media servers, enable mock mode:

```bash
export FOXHOLE_MOCK_MODE=1
uvicorn agent.main:app --reload
```
This mode intercepts tool calls and returns deterministic fake data from `tests/fixtures/mock-data.json`.

## Docker Compose

Copy the Compose env template and start the deployment skeleton:

```bash
cp iac/compose/.env.example iac/compose/.env
docker compose -f iac/compose/docker-compose.yml config
docker compose -f iac/compose/docker-compose.yml up --build
```

See `docs/deployment/docker-compose.md` for socket proxy details and the Stage 2 override.

## Safety Model

Foxhole starts in read-only mode. Optional integration credentials can be omitted while developing the core API. Missing Plex, Sonarr, Radarr, Tautulli, Overseerr, Pi-hole, Docker, or Proxmox settings should disable those integrations instead of preventing the API from starting.

Secrets are treated as configuration, not diagnostics. Health and readiness responses must not expose tokens, API keys, passwords, or webhook secrets.

## Repository Layout

```text
agent/          FastAPI app, auth, settings, and orchestration code
tools/          Read-only integration tool implementations
workers/        Celery tasks and background alert jobs
schemas/        Shared schema artifacts for API, tools, UI, and docs
iac/            Docker Compose, Proxmox, LXC, Ansible, and systemd assets
docs/           Architecture and operator documentation
tests/          Unit and API tests
```

## Roadmap

Phase 5 adds media-service diagnostics. Telegram alert fanout and the web UI follow after the diagnostic workflow is reliable.
