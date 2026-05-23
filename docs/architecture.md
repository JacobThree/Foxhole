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

## Configuration & Opt-In Modules

Foxhole utilizes an **opt-in modular architecture**. All integrations (Plex, Docker, Proxmox, etc.) are disabled by default. 

Settings are loaded via Pydantic from environment variables (`FOXHOLE_*` prefix) and optional config files under `/etc/homelab-agent`. To activate a module, you must explicitly set its enabled flag (e.g., `FOXHOLE_PLEX_ENABLED=true`). 

If a module is not enabled, the backend dynamically excludes its capabilities from the LLM Tool Registry, preserving token context and ensuring the agent respects your privacy and environment boundaries.

**Dashboard Integration:**
Users can interactively toggle and configure these modules directly from the Next.js Dashboard. The UI submits payload data to the `PATCH /settings` REST endpoint, which securely writes to the local `.env` file and purges the internal caches to reload the tool registry live, requiring no restarts. Redacted configuration summaries are safe to include in health, readiness, logs, and support output.

## Capability And Manifest Metadata

Every registered tool exposes stable capability IDs such as `containers.list`,
`media.arr.queue.read`, `monitoring.monitors.read`, and
`reverse_proxy.routes.diagnose`. The registry also records each tool's owning
integration and read/write category. The OpenAI-compatible tool schema remains
unchanged; capability metadata is used by permissions views, routing, and future
plugin/MCP surfaces.

Built-in integrations expose manifest metadata through `/integration-manifests`.
Each manifest includes:

- `id`, `name`, `version`, and `category`
- required and optional config keys, with secrets redacted
- exposed capabilities and tool definitions
- input/output schemas and safety levels
- resource URIs, event types, and diagnostic bundles
- MCP adapter notes for future resource/tool mapping

Manifests are metadata around existing integrations. They do not change runtime
tool behavior or grant write access.

## API Foundation

The API exposes unauthenticated process health at `/healthz`, authenticated readiness at `/readyz`, and a shared bearer-token dependency for future protected routes. Readiness checks local configuration and Redis connectivity without calling external homelab services.
