# Foxhole

Foxhole is a read-only-first homelab diagnostic agent for self-hosters. It is designed to inspect common services such as Proxmox, Docker, Plex, Sonarr, Radarr, Tautulli, Overseerr, Pi-hole, Unbound, and local network devices, then explain what it sees through an API that can later power chat, alerts, and a web UI.

The first milestone is intentionally conservative: collect diagnostics, expose health and readiness checks, and prepare for Telegram alerts without restarting containers, changing media server settings, migrating LXCs, or editing network configuration. Write actions will be added later behind explicit human confirmation and audit logging.

## Current Status

Phase 1 builds the foundation:

- Python package scaffold for the agent, tools, workers, schemas, deployment artifacts, and docs.
- Pydantic settings with redacted secret output.
- FastAPI shell with health, readiness, and bearer-token protection.
- Test, lint, and type-check commands for contributors.

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

## Safety Model

Foxhole starts in read-only mode. Optional integration credentials can be omitted while developing the core API. Missing Plex, Sonarr, Radarr, Tautulli, Overseerr, Pi-hole, Docker, or Proxmox settings should disable those integrations instead of preventing the API from starting.

Secrets are treated as configuration, not diagnostics. Health and readiness responses must not expose tokens, API keys, passwords, or webhook secrets.

## Repository Layout

```text
agent/          FastAPI app, auth, settings, and future orchestration code
tools/          Read-only integration tool implementations
workers/        Celery tasks and background alert jobs
schemas/        Shared schema artifacts for API, tools, UI, and docs
deploy/         Docker, Proxmox, and systemd deployment assets
docs/           Architecture and operator documentation
tests/          Unit and API tests
```

## Roadmap

Phase 2 adds the LLM router and typed tool registry. Later phases add read-only tool families, Telegram alert fanout, deployment recipes, and a web UI. Guarded write tools come after the diagnostic workflow is reliable.

