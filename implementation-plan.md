---
name: foxhole-homelab-agent-implementation-plan
description: Implementation plan for the Foxhole / HomelabGPT self-hosted homelab agent.
related_context:
  - FoxHole reseach.md
  - idea.md
  - rules/planning-and-task-breakdown.md
---

# Implementation Plan: Foxhole Homelab Agent

Derived from `FoxHole reseach.md` and `idea.md`. Methodology follows `rules/planning-and-task-breakdown.md`.

## Overview

Build an open-source homelab management agent that can inspect, diagnose, and eventually remediate common self-hosting problems across Proxmox, Docker, Plex, Sonarr, Radarr, Tautulli, Overseerr, Pi-hole, Unbound, and local network devices. The first usable milestone is a read-only diagnostic agent with Telegram alerts. Write actions such as container restarts, Portainer redeploys, Proxmox LXC migration, and Sonarr/Radarr setting updates are added later behind explicit human confirmation and audit logging.

## Dependency Graph

```text
Project scaffold + config model
        |
        |-- Typed schemas + tool registry
        |       |
        |       |-- LLM router + tool argument correction
        |       |       |
        |       |       `-- Chat/orchestrator API
        |       |
        |       |-- Read-only tool families
        |       |       |-- Docker / Portainer
        |       |       |-- Proxmox
        |       |       |-- Plex / *Arr / Tautulli / Overseerr
        |       |       `-- Pi-hole / Unbound / LAN scan
        |       |
        |       `-- Guarded write tools
        |
        |-- Deployment artifacts
        |       |-- Docker Compose + socket proxy
        |       |-- Proxmox LXC bootstrap
        |       `-- Debian / Ubuntu systemd install
        |
        |-- Celery + Redis background jobs
        |       `-- Telegram alerts + event history
        |
        `-- Web UI
                |-- Dashboard
                |-- Chat
                |-- Alerts
                `-- Settings
```

Implementation order should build foundations first, then deliver vertical diagnostic slices one service family at a time. Each slice should expose a typed tool, tests, API registration, and at least one manual verification path.

## Architecture Decisions

- **Python/FastAPI backend first.** The agent API, tool registry, and scheduler are the core product. The UI depends on these contracts and should come after the API is stable.
- **LiteLLM is the LLM provider boundary.** Hosted providers, vLLM, and Ollama are configured through model aliases such as `agent-primary`, `agent-local`, and `agent-vllm`.
- **Pydantic v2 schemas define all tool I/O.** Every tool input and output should be typed, testable, and serializable before it is exposed to the LLM.
- **Read-only first, gated writes second.** Stage 1 must not restart containers, edit media settings, migrate LXCs, or change network configuration. Stage 2 adds confirmed writes. Stage 3 adds narrowly scoped autonomous remediation.
- **Docker access goes through `tecnativa/docker-socket-proxy`.** The agent never mounts the Docker socket directly.
- **Proxmox access uses a dedicated token.** Start with audit-only privileges. Add `VM.Migrate` only when the migration task is implemented and tested.
- **Background work uses Celery 5 and Redis 7.** Scheduled checks, scans, and alert fanout should not block chat or HTTP requests.
- **Telegram is the first alert destination.** Keep the alert dispatcher pluggable so Discord, SMTP, or webhooks can be added without changing task logic.
- **No broad network scanning.** Nmap tools must reject public IP ranges and only allow RFC1918 targets.
- **Repository polish is part of the product.** README, examples, command naming, and docs should feel intentionally written for self-hosters, not like generic generated scaffolding.

## Task List

### Phase 1: Foundation

### Task 1: Create the repository scaffold

**Description:** Create the initial project layout for backend, tools, workers, deployment artifacts, schemas, docs, and future UI. Add a short product README that states what the agent does, what it does not do yet, and the read-only-first safety model.

**Acceptance criteria:**

- [x] Root project contains backend, tool, worker, schema, deployment, and docs directories matching the planned structure.
- [x] README explains the product in self-hosting language and avoids placeholder boilerplate.
- [x] `.env.example` lists required variables for providers, Proxmox, Docker, Telegram, Plex, Sonarr, Radarr, Tautulli, Overseerr, and Pi-hole.

**Verification:**

- [x] Manual check: directory tree matches this plan.
- [x] Manual check: a new contributor can identify the first install path from README.

**Dependencies:** None

**Files likely touched:**

- `README.md`
- `.env.example`
- `agent/__init__.py`
- `tools/__init__.py`
- `workers/__init__.py`
- `docs/architecture.md`

**Estimated scope:** Medium

---

### Task 2: Add Python packaging, linting, and test harness

**Description:** Add Python project metadata and developer tooling for FastAPI, Pydantic v2, LiteLLM, Instructor, Celery, Redis, httpx, Docker SDK, proxmoxer, python-telegram-bot, and pytest. Configure ruff and mypy conservatively so the codebase starts clean.

**Acceptance criteria:**

- [x] Dependencies are pinned or bounded in `pyproject.toml`.
- [x] `pytest`, `ruff`, and `mypy` commands are documented.
- [x] A minimal import test passes for `agent`, `tools`, and `workers`.

**Verification:**

- [x] Tests pass: `pytest`
- [x] Lint passes: `ruff check .`
- [x] Type check passes: `mypy agent tools workers`

**Dependencies:** Task 1

**Files likely touched:**

- `pyproject.toml`
- `requirements.txt` or lockfile if chosen
- `tests/test_imports.py`
- `README.md`

**Estimated scope:** Small

---

### Task 3: Implement settings and secret loading

**Description:** Add a Pydantic settings layer that reads environment variables and optional config files from `/etc/homelab-agent`. Separate required, optional, and write-action settings so read-only deployments can start with fewer secrets.

**Acceptance criteria:**

- [x] Settings validate provider, Redis, API auth, and integration environment variables.
- [x] Missing optional integrations do not crash the whole app.
- [x] Config redaction prevents tokens and API keys from appearing in logs or health output.

**Verification:**

- [x] Tests cover valid config, missing optional integration config, and secret redaction.
- [x] Manual check: `python -m agent.settings` or equivalent prints redacted config summary.

**Dependencies:** Task 2

**Files likely touched:**

- `agent/settings.py`
- `.env.example`
- `tests/agent/test_settings.py`
- `docs/configuration.md`

**Estimated scope:** Medium

---

### Task 4: Add FastAPI app shell, auth, and health endpoints

**Description:** Build the minimal backend with `/healthz`, `/readyz`, and authenticated API dependencies. Readiness should check Redis connectivity and basic settings validity without calling external homelab services.

**Acceptance criteria:**

- [x] `/healthz` returns process health without requiring auth.
- [x] `/readyz` checks Redis and settings without leaking secrets.
- [x] Protected routes reject missing or invalid bearer tokens.

**Verification:**

- [x] Tests pass: `pytest tests/agent/test_main.py tests/agent/test_auth.py`
- [x] Manual check: `uvicorn agent.main:app --reload` starts locally.

**Dependencies:** Task 3

**Files likely touched:**

- `agent/main.py`
- `agent/auth.py`
- `agent/settings.py`
- `tests/agent/test_main.py`
- `tests/agent/test_auth.py`

**Estimated scope:** Medium

### Checkpoint: Foundation

- [x] `pytest`, `ruff check .`, and `mypy agent tools workers` pass.
- [x] FastAPI starts and returns healthy status.
- [x] README and `.env.example` are accurate enough for a read-only local start.

---

### Phase 2: LLM and Tool Runtime

### Task 5: Implement LiteLLM router configuration

**Description:** Add the LiteLLM client wrapper and router config with provider aliases for hosted models, vLLM, and Ollama. Support runtime override of `api_base`, `api_key`, and model only through validated settings.

**Acceptance criteria:**

- [x] `agent-primary`, `agent-local`, and `agent-vllm` aliases are documented.
- [x] Router timeouts, retries, and fallbacks are configured.
- [x] Tests can replace the LiteLLM client with a fake client.

**Verification:**

- [x] Tests pass: `pytest tests/agent/llm`
- [x] Manual check: dry-run config validation succeeds without real provider calls.

**Dependencies:** Task 3

**Files likely touched:**

- `agent/llm/client.py`
- `agent/llm/router_config.yaml`
- `agent/settings.py`
- `tests/agent/llm/test_client.py`

**Estimated scope:** Medium

---

### Task 6: Build typed tool schemas and registry

**Description:** Create the base `ToolSpec`, tool registration decorator, Pydantic schema export, and a common `ToolResult` envelope containing success, data, error, duration, and write-action metadata.

**Acceptance criteria:**

- [x] Tools register by name and expose OpenAI-compatible JSON schema.
- [x] Duplicate tool names fail at startup.
- [x] Tool results have a stable schema for API, UI, and logs.

**Verification:**

- [x] Tests pass: `pytest tests/agent/tools/test_registry.py`
- [x] Manual check: registry can list available tools and schemas.

**Dependencies:** Task 2

**Files likely touched:**

- `agent/tools/base.py`
- `agent/tools/registry.py`
- `schemas/python/chat.py`
- `tests/agent/tools/test_registry.py`

**Estimated scope:** Medium

---

### Task 7: Add strict tool argument parsing and correction

**Description:** Implement strict JSON parsing, Pydantic validation, and a bounded correction loop for malformed LLM tool arguments. Include a final balanced-object extraction fallback only for read-only tools.

**Acceptance criteria:**

- [x] Valid arguments parse without LLM correction.
- [x] Invalid arguments retry with validation error context.
- [x] Corrections are capped and observable in logs.

**Verification:**

- [x] Tests pass: `pytest tests/agent/tools/test_argument_parsing.py`
- [x] Manual check: malformed JSON fixture is corrected or rejected deterministically.

**Dependencies:** Tasks 5, 6

**Files likely touched:**

- `agent/tools/base.py`
- `agent/llm/client.py`
- `tests/agent/tools/test_argument_parsing.py`

**Estimated scope:** Small

---

### Task 8: Implement the orchestrator and chat endpoint

**Description:** Add the agent loop that receives a user message, asks the model for tool calls, executes registered tools, and returns a final answer with cited tool outputs. Store an in-memory or Redis-backed conversation trace for debugging.

**Acceptance criteria:**

- [x] `/chat` accepts authenticated messages and returns an answer.
- [x] Tool calls are executed only through the registry.
- [x] Final answers distinguish observed tool output from model inference.

**Verification:**

- [x] Tests pass: `pytest tests/agent/test_chat.py tests/agent/test_orchestrator.py`
- [x] Manual check: fake LLM can call a fake diagnostic tool end-to-end.

**Dependencies:** Tasks 5, 6, 7

**Files likely touched:**

- `agent/orchestrator.py`
- `agent/main.py`
- `schemas/python/chat.py`
- `tests/agent/test_orchestrator.py`
- `tests/agent/test_chat.py`

**Estimated scope:** Medium

---

### Task 9: Add write-action safety gates

**Description:** Define a shared write-action policy for operations that restart services, redeploy stacks, migrate LXCs, edit *Arr profiles, or change network state. Require explicit confirmation tokens in Stage 2 and deny all writes in Stage 1.

**Acceptance criteria:**

- [x] Each tool declares `read_only`, `requires_confirmation`, or `autonomous_allowed`.
- [x] Unconfirmed write attempts return a structured confirmation request.
- [x] Audit log records requested action, caller, arguments, confirmation status, and result.

**Verification:**

- [x] Tests pass: `pytest tests/agent/test_write_policy.py`
- [x] Manual check: fake restart tool cannot run without confirmation.

**Dependencies:** Task 6

**Files likely touched:**

- `agent/safety.py`
- `agent/tools/base.py`
- `agent/orchestrator.py`
- `schemas/python/chat.py`
- `tests/agent/test_write_policy.py`

**Estimated scope:** Medium

### Checkpoint: Agent Runtime

- [x] Fake chat flow works end-to-end with typed tool calls.
- [x] Read-only mode blocks every write-class tool.
- [x] Tool call traces are available for debugging.

---

### Phase 3: Deployment Foundations

### Task 10: Add Docker Compose deployment with socket proxy

**Description:** Create a Compose stack for FastAPI, Celery worker, Celery beat, Redis, Flower, and `tecnativa/docker-socket-proxy`. The proxy should expose only the minimum endpoints required for read-only diagnostics in Stage 1.

**Acceptance criteria:**

- [x] Compose starts Redis, API, worker, beat, Flower, and socket proxy.
- [x] Socket proxy network is internal and not bound to a public interface.
- [x] Stage 1 proxy config blocks write endpoints such as exec, image build, volume mutation, and container delete.

**Verification:**

- [x] Build succeeds: `docker compose -f iac/compose/docker-compose.yml config`
- [x] Manual check: `/healthz` is reachable on localhost after compose up.
- [x] Manual check: blocked Docker operation returns 403 through the proxy.

**Dependencies:** Tasks 4, 9

**Files likely touched:**

- `iac/compose/docker-compose.yml`
- `iac/compose/.env.example`
- `iac/compose/socket-proxy.stage2.yml`
- `docs/deployment/docker-compose.md`

**Estimated scope:** Medium

---

### Task 11: Add Proxmox API token helper

**Description:** Add a script and docs for creating the `homelab-agent@pve` user, `HomelabAgent` role, audit-only ACLs, and optional `VM.Migrate` privilege for Stage 2. Include the `--privsep 0` requirement prominently.

**Acceptance criteria:**

- [x] Script creates or updates the user, role, ACL, and token without granting power or allocation privileges.
- [x] Docs explain the Stage 1 and Stage 2 privilege difference.
- [x] Token output instructions avoid storing secrets in shell history where possible.

**Verification:**

- [x] Shell syntax passes: `bash -n iac/proxmox/create-api-token.sh`
- [x] Manual review: privileges are limited to audit roles plus optional `VM.Migrate`.

**Dependencies:** Task 1

**Files likely touched:**

- `iac/proxmox/create-api-token.sh`
- `docs/deployment/proxmox-permissions.md`
- `.env.example`

**Estimated scope:** Small

---

### Task 12: Add Proxmox LXC bootstrap installer

**Description:** Create the community-scripts-style LXC bootstrap and inside-container installer for Debian 12. Install Python, Docker client dependencies, nmap, systemd units, config directories, and the agent service.

**Acceptance criteria:**

- [x] Bootstrap exposes CPU, RAM, disk, OS, version, unprivileged, and tag variables.
- [x] Inside-container installer creates an unprivileged `agent` user and `/opt/homelab-agent`.
- [x] Systemd unit uses hardening options and reads `/etc/homelab-agent/foxhole.env`.

**Verification:**

- [x] Shell syntax passes: `bash -n iac/lxc/install-homelab-agent.sh iac/lxc/install/homelab-agent-install.sh`
- [x] Manual review: installer does not require privileged container mode by default.
- [x] Manual check on Proxmox test node before release.

**Dependencies:** Tasks 10, 11

**Files likely touched:**

- `iac/lxc/install-homelab-agent.sh`
- `iac/lxc/install/homelab-agent-install.sh`
- `iac/lxc/systemd/homelab-agent.service`
- `docs/deployment/proxmox-lxc.md`

**Estimated scope:** Medium

---

### Task 13: Add Debian and Ubuntu server install path

**Description:** Add a non-Proxmox install path for a regular Debian or Ubuntu server. Prefer an idempotent Ansible playbook plus a manual systemd fallback.

**Acceptance criteria:**

- [x] Ansible inventory and playbook install Python runtime, config directories, and systemd service.
- [x] Manual install docs cover Debian 12 and current Ubuntu LTS.
- [x] Service user and filesystem permissions match the LXC install path.

**Verification:**

- [x] Ansible syntax check passes: `ansible-playbook --syntax-check iac/ansible/playbook.yml`
- [x] Manual review: no secrets are committed.

**Dependencies:** Task 12

**Files likely touched:**

- `iac/ansible/inventory.yml`
- `iac/ansible/playbook.yml`
- `iac/ansible/roles/agent/tasks/main.yml`
- `docs/deployment/debian-ubuntu.md`

**Estimated scope:** Medium

---

### Task 14: Add CI and container build

**Description:** Add GitHub Actions for lint, test, type check, Docker build, and optional GHCR publish on tags. CI should run without real homelab credentials.

**Acceptance criteria:**

- [x] Pull requests run tests, linting, type checking, and container build.
- [x] Integration tests use fakes or fixtures, not live Proxmox or media services.
- [x] Release workflow publishes a versioned container image only on tags.

**Verification:**

- [x] Local check: same commands documented in README pass.
- [x] GitHub Actions check is green on the first PR that adds CI.

**Dependencies:** Tasks 2, 4, 10

**Files likely touched:**

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `Dockerfile`
- `.dockerignore`
- `README.md`

**Estimated scope:** Medium

### Checkpoint: Deployable Skeleton

- [x] API, worker, beat, Redis, and socket proxy start from Compose.
- [x] LXC and Debian/Ubuntu installation paths are documented.
- [x] CI verifies backend, tests, types, and container build.

---

### Phase 4: Infrastructure Tool Families

### Task 15: Implement Docker read-only diagnostics

**Description:** Add Docker tools for listing containers, inspecting health/status, reading bounded logs, showing image/tag metadata, and detecting restart loops. Use `DOCKER_HOST=tcp://socket-proxy:2375`.

**Acceptance criteria:**

- [x] Tool returns container id, name, image, status, health, labels, ports, and restart count.
- [x] Log reads require explicit line limits and max byte limits.
- [x] Tool handles socket proxy 403 responses as permission errors, not crashes.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_docker_tool.py`
- [x] Manual check: diagnostics work against the Compose socket proxy.

**Dependencies:** Tasks 6, 10

**Files likely touched:**

- `tools/docker_tool.py`
- `schemas/python/docker.py`
- `agent/tools/registry.py`
- `tests/tools/test_docker_tool.py`

**Estimated scope:** Medium

---

### Task 16: Add guarded Docker restart actions

**Description:** Add confirmed start, stop, and restart actions for containers. Keep them disabled in Stage 1 and enabled only when the socket proxy Stage 2 override and write policy allow them.

**Acceptance criteria:**

- [x] Restart action requires confirmation and timeout bounds.
- [x] Tool refuses container exec, image build, volume changes, and delete operations.
- [x] Audit entry records old status, requested action, and resulting status.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_docker_actions.py`
- [x] Manual check: unconfirmed restart returns confirmation request.

**Dependencies:** Tasks 9, 15

**Files likely touched:**

- `tools/docker_tool.py`
- `schemas/python/docker.py`
- `tests/tools/test_docker_actions.py`
- `iac/compose/socket-proxy.stage2.yml`

**Estimated scope:** Small

---

### Task 17: Implement Portainer endpoint and stack tools

**Description:** Add Portainer API integration for listing endpoints, listing stacks, reading stack details, and triggering confirmed Git redeploys. Prefer API access tokens over username/password.

**Acceptance criteria:**

- [x] Read tools list endpoints and stacks.
- [x] Redeploy action requires confirmation and endpoint/stack ids.
- [x] Auth supports API token first and JWT fallback second.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_portainer_tool.py`
- [x] Manual check against a test Portainer endpoint if available.

**Dependencies:** Tasks 6, 9

**Files likely touched:**

- `tools/portainer_tool.py`
- `schemas/python/portainer.py`
- `tests/tools/test_portainer_tool.py`
- `docs/integrations/portainer.md`

**Estimated scope:** Medium

---

### Task 18: Implement Proxmox inventory, storage, and migration tools

**Description:** Add Proxmox tools for node status, LXC inventory, VM inventory, storage usage, backup job visibility, and confirmed LXC migration. Migration should require `VM.Migrate` and explicit confirmation.

**Acceptance criteria:**

- [x] Read-only tools work with audit-only token privileges.
- [x] Storage output includes used percentage, used GB, total GB, and datastore type.
- [x] Migration tool refuses to run unless write policy and confirmation are satisfied.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_proxmox_tool.py`
- [x] Manual check: audit-only token can run inventory and storage tools.
- [x] Manual check: migration fails clearly without `VM.Migrate`.

**Dependencies:** Tasks 9, 11

**Files likely touched:**

- `tools/proxmox_tool.py`
- `schemas/python/proxmox.py`
- `tests/tools/test_proxmox_tool.py`
- `docs/integrations/proxmox.md`

**Estimated scope:** Medium

---

### Task 19: Implement backup and storage health summary

**Description:** Add a higher-level diagnostic that combines Proxmox storage, backup job status, datastore free space, and local filesystem checks into a single "are my backups and storage healthy?" answer.

**Acceptance criteria:**

- [x] Summary identifies stale backups, failed jobs, and storage above configured thresholds.
- [x] Thresholds are configurable per datastore.
- [x] Output includes concrete next actions without performing writes.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_backup_storage_health.py`
- [x] Manual check: fake backup fixture produces expected warnings.

**Dependencies:** Task 18

**Files likely touched:**

- `tools/backup_tool.py`
- `schemas/python/backups.py`
- `tests/tools/test_backup_storage_health.py`
- `docs/integrations/backups.md`

**Estimated scope:** Medium

### Checkpoint: Infrastructure Diagnostics

- [x] User can ask "what is broken in Docker?" and get observed container/log facts.
- [x] User can ask "is Proxmox storage healthy?" and get datastore and backup facts.
- [x] No write action can run without explicit confirmation.

---

### Phase 5: Media Server Diagnostics

### Task 20: Implement Plex native LXC diagnostics

**Description:** Add Plex diagnostics for active sessions, transcode decisions, hardware acceleration availability, bounded Plex log analysis, and common SQLite warnings. Support native Plex installs where logs are on the LXC filesystem.

**Acceptance criteria:**

- [x] Tool reports active sessions, users, titles, player, direct play vs transcode, and hardware transcode state.
- [x] Log parser detects SQLite busy, database locked, slow SQL, and transcode errors.
- [x] Tool explains buffering risk using observed session and hardware data.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_plex_tool.py`
- [x] Manual check: missing Plex log path returns a clear unavailable state.

**Dependencies:** Task 6

**Files likely touched:**

- `tools/plex_tool.py`
- `schemas/python/plex.py`
- `tests/tools/test_plex_tool.py`
- `docs/integrations/plex.md`

**Estimated scope:** Medium

---

### Task 21: Add Plex debug mode guidance and safe commands

**Description:** Add a read-only Plex troubleshooting workflow that can report whether debug logging appears enabled, suggest how to enable it manually, and run non-destructive checks. Do not toggle Plex settings automatically in MVP.

**Acceptance criteria:**

- [x] Tool distinguishes "can inspect" from "needs manual action".
- [x] Suggested commands are documented and not executed automatically.
- [x] Output includes when to check CPU, GPU, bandwidth, client codec support, and database health.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_plex_debug_guidance.py`
- [x] Manual review: guidance does not imply unsupported automatic Plex mutation.

**Dependencies:** Task 20

**Files likely touched:**

- `tools/plex_tool.py`
- `docs/runbooks/plex-buffering.md`
- `tests/tools/test_plex_debug_guidance.py`

**Estimated scope:** Small

---

### Task 22: Implement Sonarr and Radarr diagnostics

**Description:** Add *Arr tools for queue, health, root folders, download clients, quality profiles, and import failure diagnosis. Detect Docker volume path mismatches between download output and configured root folders.

**Acceptance criteria:**

- [x] Tool reports queue size, warnings, health issues, and root folder paths.
- [x] Import mismatch diagnosis includes title, output path, expected roots, and status messages.
- [x] API auth uses `X-Api-Key` and handles Sonarr/Radarr independently.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_arr_tool.py`
- [x] Manual check: fixture with bad volume mapping produces mismatch diagnosis.

**Dependencies:** Task 6

**Files likely touched:**

- `tools/arr_tool.py`
- `schemas/python/arr.py`
- `tests/tools/test_arr_tool.py`
- `docs/integrations/sonarr-radarr.md`

**Estimated scope:** Medium

---

### Task 23: Add guarded Sonarr and Radarr write actions

**Description:** Add confirmed write tools for updating selected settings such as quality profiles or queue item actions. These must require confirmation, show before/after payloads, and avoid broad automatic rewrites.

**Acceptance criteria:**

- [x] Write actions require confirmation and target a specific service and resource id.
- [x] Before/after diff is shown before execution.
- [x] Tool refuses unsupported bulk profile rewrites.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_arr_actions.py`
- [x] Manual check: unconfirmed profile update returns confirmation request.

**Dependencies:** Tasks 9, 22

**Files likely touched:**

- `tools/arr_tool.py`
- `schemas/python/arr.py`
- `tests/tools/test_arr_actions.py`
- `docs/runbooks/arr-import-failures.md`

**Estimated scope:** Medium

---

### Task 24: Implement Tautulli and Overseerr observability

**Description:** Add Tautulli and Overseerr tools for recent history, failed requests, version/staleness status, and a merged fault timeline that can help explain media server failures.

**Acceptance criteria:**

- [x] Tautulli uses `?apikey=` and Overseerr uses `X-Api-Key`.
- [x] Fault timeline merges events by timestamp and source.
- [x] Overseerr filter limitations are documented and handled by cross-checking status fields where possible.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_observability_tool.py`
- [x] Manual check: empty history returns an empty timeline, not an error.

**Dependencies:** Tasks 20, 22

**Files likely touched:**

- `tools/observability_tool.py`
- `schemas/python/observability.py`
- `tests/tools/test_observability_tool.py`
- `docs/integrations/tautulli-overseerr.md`

**Estimated scope:** Medium

### Checkpoint: Media Diagnostics

- [x] User can ask why Plex users are buffering and get Plex, Tautulli, and resource facts.
- [x] User can ask why Sonarr/Radarr did not import and get queue, health, root folder, and path mismatch facts.
- [x] Media write actions remain confirmation-gated.

---

### Phase 6: Network and Security Diagnostics

### Task 25: Implement Pi-hole and Unbound health tools

**Description:** Add Pi-hole summary, recent blocked domains, bounded query reads, and Unbound stats. Use Pi-hole v5 API syntax for MVP and isolate v6 migration in docs.

**Acceptance criteria:**

- [x] Pi-hole requests include `auth` for every endpoint.
- [x] Query reads require a strict limit and never dump unbounded history into LLM context.
- [x] Unbound stats parse key/value output into typed metrics.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_network_tool.py`
- [x] Manual check: missing Pi-hole token produces a clear auth error.

**Dependencies:** Task 6

**Files likely touched:**

- `tools/network_tool.py`
- `schemas/python/network.py`
- `tests/tools/test_network_tool.py`
- `docs/integrations/pihole-unbound.md`

**Estimated scope:** Medium

---

### Task 26: Implement RFC1918-only network scanning

**Description:** Add nmap host discovery and limited service detection. The tool must reject non-private ranges, require configured allowed subnets, and support a known-device allowlist for unknown MAC alerts.

**Acceptance criteria:**

- [x] Public IP ranges are refused before nmap runs.
- [x] Scans are limited to configured private subnets.
- [x] Results include IP, hostname, MAC, vendor, state, and limited service metadata.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_network_scanning.py`
- [x] Manual check: `8.8.8.8` and public CIDRs are rejected.

**Dependencies:** Tasks 9, 25

**Files likely touched:**

- `tools/network_tool.py`
- `schemas/python/network.py`
- `tests/tools/test_network_scanning.py`
- `docs/runbooks/network-scanning.md`

**Estimated scope:** Medium

---

### Task 27: Add security posture checks

**Description:** Add read-only checks for common homelab security risks: exposed admin ports, containers running privileged, missing restart policies, Docker containers with host networking, old images, and Proxmox token privilege drift.

**Acceptance criteria:**

- [x] Security summary reports findings with severity and observed evidence.
- [x] Checks do not require write privileges.
- [x] Findings include remediation guidance but do not auto-fix.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_security_checks.py`
- [x] Manual check: fixture with privileged container produces high severity finding.

**Dependencies:** Tasks 15, 18, 26

**Files likely touched:**

- `tools/security_tool.py`
- `schemas/python/security.py`
- `tests/tools/test_security_checks.py`
- `docs/runbooks/security-hardening.md`

**Estimated scope:** Medium

### Checkpoint: Network and Security

- [x] User can ask whether the network looks healthy and get Pi-hole, Unbound, and LAN scan facts.
- [x] Unknown device detection works from fixtures.
- [x] Security posture checks are evidence-based and read-only.

---

### Phase 7: Background Monitoring and Alerts

### Task 28: Add Celery app, queues, and beat schedule

**Description:** Add Celery configuration for default and scan queues, Redis broker/result backend, beat schedules, retry settings, and task routing. Start with read-only periodic checks.

**Acceptance criteria:**

- [x] Worker imports task modules without side effects that call external services.
- [x] Beat schedules container health, storage thresholds, *Arr import checks, Plex DB health, and rogue MAC scans.
- [x] Tasks return structured results for logs and alerting.

**Verification:**

- [x] Tests pass: `pytest tests/workers`
- [x] Manual check: Celery worker starts from Compose.

**Dependencies:** Tasks 10, 15, 19, 20, 22, 26

**Files likely touched:**

- `workers/app.py`
- `workers/celeryconfig.py`
- `workers/tasks.py`
- `tests/workers/test_tasks.py`

**Estimated scope:** Medium

---

### Task 29: Implement Telegram alerts

**Description:** Add Telegram alert rendering with MarkdownV2 escaping, message chunking, and templates for container crash, storage threshold, unknown MAC, *Arr import mismatch, and Plex database warnings.

**Acceptance criteria:**

- [x] Every alert template escapes MarkdownV2 special characters.
- [x] Messages longer than Telegram limits are chunked safely.
- [x] Alert send failures are logged and retried by Celery where appropriate.

**Verification:**

- [x] Tests pass: `pytest tests/agent/alerts/test_telegram.py`
- [x] Manual check: test alert sends to configured chat.

**Dependencies:** Task 28

**Files likely touched:**

- `agent/alerts/telegram.py`
- `agent/alerts/dispatcher.py`
- `schemas/python/alerts.py`
- `tests/agent/alerts/test_telegram.py`

**Estimated scope:** Medium

---

### Task 30: Add event and audit history

**Description:** Store alert events, tool calls, confirmations, and write results in a lightweight event history. Use Redis streams for MVP or SQLite if durable local history is required by the deployment target.

**Acceptance criteria:**

- [x] Each event has id, timestamp, type, severity, source, payload summary, and correlation id.
- [x] Secrets are redacted before storage.
- [x] API can list recent events for the future UI.

**Verification:**

- [x] Tests pass: `pytest tests/agent/test_events.py`
- [x] Manual check: a fake alert appears in event history.

**Dependencies:** Tasks 8, 9, 29

**Files likely touched:**

- `agent/events.py`
- `agent/main.py`
- `schemas/python/alerts.py`
- `tests/agent/test_events.py`

**Estimated scope:** Medium

---

### Task 31: Add Stage 3 autonomous remediation hooks

**Description:** Add disabled-by-default remediation hooks for narrowly scoped incidents such as restarting a container that crashed more than three times in ten minutes. Keep every autonomous action configurable and alert with a receipt.

**Acceptance criteria:**

- [x] Autonomous actions are globally disabled by default.
- [x] Each autonomous rule has thresholds, cooldown, and max actions per window.
- [x] Every autonomous action writes an audit event and sends a Telegram receipt.

**Verification:**

- [x] Tests pass: `pytest tests/workers/test_remediation.py`
- [x] Manual check: disabled autonomous rules never execute writes.

**Dependencies:** Tasks 9, 16, 28, 29, 30

**Files likely touched:**

- `workers/remediation.py`
- `workers/tasks.py`
- `agent/safety.py`
- `tests/workers/test_remediation.py`

**Estimated scope:** Medium

### Checkpoint: Monitoring

- [x] Scheduled checks run from Celery.
- [x] Telegram alerts render correctly and redact secrets.
- [x] Event history supports audit and future UI pages.

---

### Phase 8: Web UI

### Task 32: Scaffold the Next.js control plane

**Description:** Add the Next.js app for dashboard, chat, alerts, and settings. Use a quiet operational interface rather than a marketing landing page. Keep API access behind the FastAPI auth model or a secure proxy route.

**Acceptance criteria:**

- [x] UI starts locally and can read backend health.
- [x] Layout includes navigation for Dashboard, Chat, Alerts, and Settings.
- [x] Design is dense, readable, and suited to repeated admin use.

**Verification:**

- [x] Build succeeds: `pnpm --dir ui build`
- [x] Lint passes: `pnpm --dir ui lint`
- [x] Manual browser check: dashboard shell loads without console errors.

**Dependencies:** Tasks 4, 30

**Files likely touched:**

- `ui/package.json`
- `ui/app/layout.tsx`
- `ui/app/page.tsx`
- `ui/lib/api-client.ts`
- `ui/components/nav.tsx`

**Estimated scope:** Medium

---

### Task 33: Build dashboard service overview

**Description:** Add dashboard cards/tables for Docker containers, Proxmox storage, backup health, media health, and network status. Use typed API responses and clear degraded/warning/healthy states.

**Acceptance criteria:**

- [x] Dashboard shows real backend data or explicit unavailable states per integration.
- [x] Status indicators are based on tool output, not model summaries.
- [x] Refresh behavior is predictable and does not spam diagnostic endpoints.

**Verification:**

- [x] Tests pass: `pnpm --dir ui test` if test runner is configured.
- [x] Manual browser check: dashboard handles both healthy and degraded fixture data.

**Dependencies:** Tasks 15, 18, 19, 24, 25, 32

**Files likely touched:**

- `ui/app/page.tsx`
- `ui/components/service-table.tsx`
- `ui/components/status-badge.tsx`
- `ui/lib/api-client.ts`

**Estimated scope:** Medium

---

### Task 34: Build chat interface with tool call visibility

**Description:** Add a chat page that streams or polls agent responses and displays tool calls, arguments, results, and confirmation requests in a compact operational format.

**Acceptance criteria:**

- [x] User can send a prompt and receive an answer.
- [x] Tool calls are visible with status, duration, and errors.
- [x] Confirmation requests present clear approve/cancel actions and never hide the target operation.

**Verification:**

- [x] Manual browser check: fake LLM flow shows tool call and final answer.
- [x] Manual browser check: write confirmation cannot be accidentally submitted twice.

**Dependencies:** Tasks 8, 9, 32

**Files likely touched:**

- `ui/app/chat/page.tsx`
- `ui/components/tool-call-card.tsx`
- `ui/components/confirmation-panel.tsx`
- `ui/lib/api-client.ts`

**Estimated scope:** Medium

---

### Task 35: Build alerts and event history pages

**Description:** Add alert and event history views with severity filters, source filters, acknowledgement state, and links back to related tool calls or remediation actions.

**Acceptance criteria:**

- [x] Alerts page lists recent events from backend history.
- [x] Filters include severity, source, and event type.
- [x] Acknowledgement action is confirmation-gated if it changes server state.

**Verification:**

- [x] Manual browser check: generated alert appears and can be filtered.
- [x] Manual browser check: secrets do not appear in event payload details.

**Dependencies:** Tasks 29, 30, 32

**Files likely touched:**

- `ui/app/alerts/page.tsx`
- `ui/components/event-table.tsx`
- `ui/lib/api-client.ts`
- `agent/main.py`

**Estimated scope:** Medium

---

### Task 36: Build settings and provider configuration UI

**Description:** Add settings pages for provider aliases, integration availability, alert destinations, allowed scan subnets, and write-action mode. Avoid exposing raw secret values after save.

**Acceptance criteria:**

- [x] Settings show configured/unconfigured status for each integration.
- [x] Secrets are write-only or redacted after save.
- [x] Write-action mode clearly shows Stage 1 read-only, Stage 2 confirmed writes, or Stage 3 autonomous rules.

**Verification:**

- [x] Manual browser check: settings load with redacted secrets.
- [x] Manual browser check: invalid subnet is rejected before save.

**Dependencies:** Tasks 3, 9, 26, 32

**Files likely touched:**

- `ui/app/settings/page.tsx`
- `ui/app/settings/providers/page.tsx`
- `ui/components/settings-form.tsx`
- `agent/main.py`

**Estimated scope:** Medium

### Checkpoint: Usable App

- [x] Dashboard, chat, alerts, and settings pages load.
- [x] Browser verification shows no console errors on primary flows.
- [x] Text fits in desktop and mobile layouts.
- [x] Write confirmations are clear and auditable.

---

### Phase 9: Documentation, Examples, and Release

### Task 37: Write integration runbooks

**Description:** Create concise runbooks for common prompts and incidents: Plex buffering, Sonarr/Radarr import failures, container crash loops, storage pressure, backup failures, unknown MAC alerts, and Pi-hole/Unbound DNS issues.

**Acceptance criteria:**

- [x] Each runbook states what the agent checks, what permissions are required, and what actions remain manual.
- [x] Runbooks include example prompts and expected evidence.
- [x] Runbooks avoid invented certainty and call out when data is unavailable.

**Verification:**

- [x] Manual review: each user concern from `idea.md` maps to at least one runbook.

**Dependencies:** Tasks 15 through 30

**Files likely touched:**

- `docs/runbooks/plex-buffering.md`
- `docs/runbooks/arr-import-failures.md`
- `docs/runbooks/container-crash-loop.md`
- `docs/runbooks/storage-and-backups.md`
- `docs/runbooks/network-security.md`

**Estimated scope:** Medium

---

### Task 38: Add demo fixtures and mock homelab mode

**Description:** Add fake service responses and a mock mode so contributors can run the UI and backend without real Proxmox, Plex, or Docker access.

**Acceptance criteria:**

- [x] Mock mode serves deterministic data for every core dashboard and chat flow.
- [x] Tests reuse the same fixtures where practical.
- [x] README includes a no-homelab demo command.

**Verification:**

- [x] Tests pass using mock fixtures.
- [x] Manual check: dashboard and chat work in mock mode.

**Dependencies:** Tasks 8, 15, 18, 20, 22, 25, 32

**Files likely touched:**

- `tests/fixtures/*.json`
- `agent/mock_mode.py`
- `tools/tests/conftest.py`
- `README.md`

**Estimated scope:** Medium

---

### Task 39: Add release packaging and versioning

**Description:** Add version metadata, container labels, changelog, release checklist, and documentation for upgrading the Compose stack, LXC install, and Debian/Ubuntu service.

**Acceptance criteria:**

- [x] Version is available from API, CLI, Docker labels, and UI footer.
- [x] Release checklist includes migration, config, backup, and rollback steps.
- [x] Upgrade docs cover Compose and systemd installs.

**Verification:**

- [x] Build succeeds: backend container and UI assets.
- [x] Manual check: version appears in `/healthz` and UI.

**Dependencies:** Tasks 14, 32

**Files likely touched:**

- `agent/version.py`
- `Dockerfile`
- `CHANGELOG.md`
- `docs/release.md`
- `ui/components/version-footer.tsx`

**Estimated scope:** Small

---

### Task 40: Run staged rollout validation

**Description:** Validate the project in three stages: read-only diagnostics, confirmed writes, then disabled-by-default autonomous remediation. Record the results in release notes before calling the MVP ready.

**Acceptance criteria:**

- [x] Stage 1 answers "what is broken right now?" correctly in five representative scenarios.
- [x] Stage 2 completes seven days with zero unintended writes.
- [x] Stage 3 rules remain disabled by default and execute only in explicit test scenarios.

**Verification:**

- [x] Manual smoke checklist in `docs/release.md` is completed.
- [x] Telegram receipts and audit history exist for every write test.
- [x] Human review approves release readiness.

**Dependencies:** Tasks 1 through 39

**Files likely touched:**

- `docs/release.md`
- `CHANGELOG.md`
- `README.md`

**Estimated scope:** Medium

### Checkpoint: MVP Release

- [x] Compose deployment works.
- [x] Proxmox LXC deployment works.
- [x] Debian/Ubuntu deployment path works or is clearly marked beta.
- [x] Core diagnostics work for Docker, Proxmox, Plex, Sonarr/Radarr, Tautulli/Overseerr, Pi-hole/Unbound, and LAN scans.
- [x] Telegram alerts work.
- [x] UI supports dashboard, chat, alerts, and settings.
- [x] All write actions are confirmation-gated or disabled by default.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Docker socket proxy still exposes sensitive container metadata | High | Keep proxy on an internal network, never bind publicly, redact env vars, document limitations clearly. |
| Proxmox token is over-privileged | High | Start audit-only, script exact privileges, add `VM.Migrate` only for Stage 2, test privilege drift in security checks. |
| Local LLM produces malformed tool calls | Medium | Pydantic validation, bounded correction loop, fallback to hosted correction model, tests with malformed fixtures. |
| Agent hallucinates root cause | High | Final answers must cite tool output and label inference separately. UI shows raw tool evidence. |
| Network scan accidentally targets public IPs | High | Enforce RFC1918 validation and configured allowed subnets before nmap execution. |
| Telegram MarkdownV2 formatting breaks alerts | Medium | Central escaping helper, unit tests for templates, chunk messages below Telegram limits. |
| Media service APIs differ by version | Medium | Version/status endpoints, fixture tests, docs for known Overseerr filter limitations and Pi-hole v6 migration. |
| UI becomes a marketing page instead of a tool | Medium | Build dashboard as first screen, use dense operational layout, avoid hero/landing page patterns. |
| Repo feels generic or generated | Medium | Write specific runbooks, real examples, coherent naming, no placeholder copy, no unused scaffolding. |
| Autonomous remediation causes unintended writes | High | Disabled by default, cooldowns, narrow rules, audit events, Telegram receipts, staged rollout gate. |

## Open Questions

- What final product name should be used consistently: `Foxhole`, `HomelabGPT`, or `homelab-agent`?
- Should the MVP include the Next.js UI, or should the first release be API plus Telegram only?
- Which auth model should protect the UI and API for the first release: single admin bearer token, local login, reverse-proxy auth, or OIDC?
- Should event history use Redis streams only, or should the project add SQLite for durable local audit history?
- Which Proxmox node and LAN subnet should be the default examples in docs?
- Should Portainer be treated as optional convenience integration or the recommended deployment control plane?
- Which write actions are allowed in Stage 2 besides container restart and Portainer redeploy?
- Should the project support Discord or email alerts in MVP, or keep Telegram as the only destination?

## Parallelization Opportunities

- **Safe to parallelize after Phase 2:** Docker diagnostics, Proxmox diagnostics, Plex diagnostics, *Arr diagnostics, Pi-hole/Unbound tools, and docs runbooks.
- **Safe to parallelize after API contracts settle:** UI dashboard, alerts page, settings page, and mock fixtures.
- **Must be sequential:** Settings model, tool registry, write policy, and orchestrator.
- **Needs coordination:** Shared schemas between backend and UI, event history format, alert envelope format, and confirmation request format.

## Verification Before Implementation

- [x] Every task has acceptance criteria.
- [x] Every task has verification steps.
- [x] Dependencies are ordered.
- [x] No task intentionally requires more than one focused implementation session.
- [x] Checkpoints exist between major phases.
- [x] Human has reviewed and approved the staged safety model.
