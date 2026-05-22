# Architecture

Foxhole is organized around a FastAPI backend, typed diagnostic tools, and background workers.

## Runtime Components

- `agent`: API endpoints, authentication, settings, LLM routing, and orchestration.
- `tools`: read-only integrations for Docker, Proxmox, media services, DNS, and LAN diagnostics.
- `workers`: Celery jobs for scheduled checks, history capture, and alert delivery.
- `schemas`: shared contracts used by the API, tools, workers, and future UI.
- `deploy`: Docker Compose, Proxmox LXC, and systemd deployment assets.

## Read-Only First

The first usable milestone does not change homelab state. Tool implementations should collect status, logs, and metadata, then return structured results. Any future write action must declare itself as a write, require confirmation, and be audit logged.

## Configuration

Settings are loaded from environment variables and optional config files under `/etc/homelab-agent`. Optional integrations should degrade cleanly when credentials are absent. Redacted configuration summaries are safe to include in health, readiness, logs, and support output.

## API Foundation

The API exposes unauthenticated process health at `/healthz`, authenticated readiness at `/readyz`, and a shared bearer-token dependency for future protected routes. Readiness checks local configuration and Redis connectivity without calling external homelab services.

