---
name: foxhole-update-plan
description: Iteration plan for turning the current Foxhole scaffold into a usable, evidence-backed homelab SRE agent.
related_context:
  - Chat-convo.md
  - implementation-plan.md
  - rules/planning-and-task-breakdown.md
---

# Implementation Plan: Foxhole Product Update

Derived from `Chat-convo.md` and the current project state. Methodology follows `rules/planning-and-task-breakdown.md`.

## Overview

Turn Foxhole from a strong MVP scaffold into a self-hosted homelab operations copilot that can safely investigate issues, show evidence for every conclusion, and only mutate systems through explicit policy gates. The first update milestone should make the product usable end-to-end: authenticated UI, live chat, live events, real scheduled diagnostics, durable audit/event history, mock demo mode, and token-aware agent execution. Later phases add plugin and integration foundations so Foxhole can grow without turning the core repo into a hardcoded pile of service-specific logic.

## Verification Review - 2026-05-23

- Verified with `rtk proxy pytest` from the repo root: 134 tests passed.
- Verified with `rtk pnpm lint` and `rtk pnpm build` from `ui/`; both completed successfully. The build emitted only the existing Next.js workspace-root warning.
- Re-verified Task 12 after SQLModel conversion with `rtk proxy mypy agent/db`, `rtk proxy ruff check agent/db`, and `rtk proxy pytest`: all passed.
- Phase 1 through Phase 6 implementation is mostly complete and checked below.
- Task 12 is complete: durable SQLite persistence now uses SQLModel/SQLAlchemy models and isolated session helpers under `agent/db/`.
- Phase 7 remains open after re-audit: tools expose safety and integration grouping, but not stable capability IDs or integration manifests; Uptime Kuma, Homepage/Homarr widget output, and Caddy are not present.

## Dependency Graph

```text
Shared evidence + event contracts
        |
        |-- UI auth client
        |       |
        |       |-- Chat UI -> /chat
        |       |-- Alerts UI -> /events
        |       `-- Dashboard -> summary endpoint
        |
        |-- Worker diagnostic result schema
        |       |
        |       |-- Docker/storage checks
        |       |-- Plex/*Arr checks
        |       `-- LAN/security checks
        |
        |-- Durable persistence
        |       |
        |       |-- Event history
        |       |-- Write audit receipts
        |       `-- Incident timelines
        |
        |-- Mock mode + evaluation fixtures
        |       |
        |       `-- Deterministic demo and regression scenarios
        |
        `-- Agent budget + capability metadata
                |
                |-- Intent-based tool loading
                |-- Tool output summarization
                `-- Plugin/integration manifest
```

Implementation order should keep vertical slices working. UI work depends on stable contracts. Worker work depends on a shared diagnostic/event envelope. Plugin growth should wait until the current integrations expose capability metadata and the agent has token-budget controls.

## Architecture Decisions

- **Evidence-backed answers are the product contract.** Chat responses should distinguish findings, checked evidence, confidence, suggested actions, risk, and confirmation requirements.
- **Deterministic diagnostics run before LLM reasoning.** Scheduled checks and diagnostic bundles should collect compact structured evidence; the LLM explains and correlates rather than parsing raw logs by default.
- **Redis remains the live event bus; SQLite becomes durable history.** Redis streams are useful for current events, but audits, incidents, and historical checks need restart-safe storage. Use SQLite by default and introduce SQLAlchemy/SQLModel now in a small `agent/db/` package with `session.py`, `models.py`, and `repositories.py`.
- **Browser auth uses an HTTP-only session cookie.** Keep bearer-token validation as the backend credential primitive, but add a small login endpoint that validates the bearer token once and sets an HTTP-only cookie for the Next.js UI. Local Compose should use `HttpOnly`, `Secure=False`, and `SameSite=Lax`; HTTPS proxy deployments should use `HttpOnly`, `Secure=True`, `SameSite=Strict`, and a `__Host-foxhole_session` cookie when possible.
- **Write safety stays central.** Stage 1 denies writes, Stage 2 requires confirmation, and Stage 3 remains disabled-by-default with narrow policy rules. Manual confirmation-token paste is the first UI flow; one-click approval should wait for durable pending actions.
- **Mock mode is a real runtime mode, not only a test fixture.** `FOXHOLE_MOCK_MODE=1` should make tools return deterministic broken-homelab scenarios for demos, tests, and UI development.
- **Token control comes before more integrations.** Intent-based tool loading, compact tool outputs, and agent budgets should land before adding many new tools.
- **Plugin manifests start as metadata around existing integrations.** Do not rewrite the registry immediately. First add capability metadata that can later support community plugins and MCP exposure. Design the metadata with MCP in mind now, but expose an MCP server only after manifests stabilize around IDs, versions, config schemas, capabilities, tools, input/output schemas, safety levels, resources, and event types.

## Task List

### Phase 1: Evidence Contracts and Authenticated UI

### Task 1: Define evidence-backed diagnosis schemas

**Description:** Add shared schemas for diagnostic findings, evidence items, suggested actions, risk levels, confidence, and agent budget metadata. These should be usable by chat responses, worker events, incidents, and UI rendering.

**Acceptance criteria:**

- [x] A diagnostic response can represent finding, evidence checked, confidence, suggested fix, risk level, and whether an action requires confirmation.
- [x] Existing `ChatResponse` remains backward compatible or has a documented migration path.
- [x] Unit tests cover serialization and redaction-safe examples.

**Verification:**

- [x] Tests pass: `pytest tests/agent tests/workers`
- [x] Manual check: example schema output is readable and does not leak secrets.

**Dependencies:** None

**Files likely touched:**

- `schemas/python/chat.py`
- `schemas/python/events.py`
- `agent/orchestrator.py`
- `tests/agent/test_chat.py`
- `tests/agent/test_orchestrator.py`

**Estimated scope:** Medium

---

### Task 2: Add HTTP-only cookie login for the Next.js API client

**Description:** Add a small login endpoint that accepts the configured bearer token, validates it, and sets an HTTP-only session cookie for browser requests. Update the UI API client to send credentials and add a small settings/login surface for entering, validating, and clearing the session.

**Acceptance criteria:**

- [x] Backend exposes a login/logout flow that sets and clears an HTTP-only cookie after validating the bearer token.
- [x] `fetchApi` sends cookie credentials for protected requests without storing the bearer token in browser-accessible storage.
- [x] UI shows a clear unauthenticated state for 401 and unconfigured-backend state for 503.
- [x] Cookie/session handling is isolated so future OIDC replacement is straightforward.
- [x] Cookie settings support local Compose and HTTPS proxy profiles: local uses `Secure=False` and `SameSite=Lax`; HTTPS uses `Secure=True`, `SameSite=Strict`, and `__Host-foxhole_session` when possible.

**Verification:**

- [x] Backend auth tests pass: `pytest tests/agent/test_auth.py tests/agent/test_main.py`
- [x] UI lint/build passes: `pnpm lint` and `pnpm build` from `ui/`.
- [x] Manual check: login sets a cookie, logout clears it, and `/readyz`, `/settings`, `/chat`, and `/events` work without exposing the bearer token to client-side JavaScript.

**Dependencies:** None

**Files likely touched:**

- `ui/lib/api-client.ts`
- `ui/app/settings/page.tsx`
- `ui/components/settings-form.tsx`
- `ui/app/settings/integrations/page.tsx`
- `agent/auth.py`
- `agent/main.py`
- `agent/settings.py`
- `tests/agent/test_auth.py`
- `tests/agent/test_main.py`

**Estimated scope:** Small-Medium

---

### Task 3: Wire the chat UI to `/chat`

**Description:** Replace static chat examples with a real conversation flow that sends user prompts to `/chat`, renders agent answers, renders `tool_traces`, and handles confirmation tokens for Stage 2 write requests.

**Acceptance criteria:**

- [x] User can submit a prompt and see the backend response without a page refresh.
- [x] Tool traces render using existing `ToolCallCard` styling.
- [x] Confirmation-required responses show the confirmation token and support manual paste/resubmit with that token.

**Verification:**

- [x] UI build passes: `pnpm build` from `ui/`.
- [x] Backend tests pass for chat and write policy: `pytest tests/agent/test_chat.py tests/agent/test_write_policy.py`
- [x] Manual check: fake/mocked chat response renders tool traces and confirmation state.

**Dependencies:** Task 1, Task 2

**Files likely touched:**

- `ui/app/chat/page.tsx`
- `ui/components/tool-call-card.tsx`
- `ui/components/confirmation-panel.tsx`
- `ui/lib/api-client.ts`
- `schemas/python/chat.py`

**Estimated scope:** Medium

---

### Checkpoint: UI Chat Usable

- [x] Backend auth-protected endpoints are reachable from the UI.
- [x] Chat page is no longer static.
- [x] Confirmation-required write attempts are visible, require manual token paste, and cannot silently execute.

---

### Phase 2: Live Dashboard and Events

### Task 4: Connect alerts page to `/events`

**Description:** Replace static alert data with the authenticated event stream reader. Normalize event severity, source, timestamp, correlation ID, and payload summary into the existing table.

**Acceptance criteria:**

- [x] Alerts page fetches recent events from `/events`.
- [x] Empty, loading, error, and unauthenticated states are handled.
- [x] Existing client-side acknowledgement remains clearly local-only or is removed until a backend acknowledgement endpoint exists.

**Verification:**

- [x] UI build passes: `pnpm build` from `ui/`.
- [x] Backend event tests pass: `pytest tests/agent/test_events.py tests/agent/test_main.py`
- [x] Manual check: inserting a Redis event makes it appear in the UI.

**Dependencies:** Task 2

**Files likely touched:**

- `ui/app/alerts/page.tsx`
- `ui/components/event-table.tsx`
- `ui/lib/api-client.ts`
- `tests/agent/test_main.py`

**Estimated scope:** Small-Medium

---

### Task 5: Add a read-only dashboard summary endpoint

**Description:** Add a backend endpoint that returns a compact summary for the dashboard: agent readiness, enabled integrations, recent event counts by severity, and latest check results. Keep this endpoint read-only and cheap.

**Acceptance criteria:**

- [x] `GET /dashboard/summary` is bearer-authenticated.
- [x] Response includes readiness, integrations, severity counts, and recent check summaries.
- [x] Endpoint does not call external homelab services directly; it reads current settings and stored events/check results.

**Verification:**

- [x] Tests pass: `pytest tests/agent/test_main.py tests/agent/test_events.py`
- [x] Manual check: response remains fast with no integrations configured.

**Dependencies:** Task 1, Task 4

**Files likely touched:**

- `agent/main.py`
- `agent/events.py`
- `schemas/python/events.py`
- `tests/agent/test_main.py`

**Estimated scope:** Medium

---

### Task 6: Replace static dashboard data

**Description:** Wire the dashboard page to the new summary endpoint and show real agent/integration/event state. Keep individual service tables for later diagnostic drilldowns.

**Acceptance criteria:**

- [x] Dashboard no longer hardcodes Docker, Proxmox, or network service rows.
- [x] Enabled and disabled integrations are visually distinguishable.
- [x] Recent critical/warning events are visible without opening the alerts page.

**Verification:**

- [x] UI build passes: `pnpm build` from `ui/`.
- [x] Manual check: dashboard reflects changes after toggling integration settings.

**Dependencies:** Task 2, Task 5

**Files likely touched:**

- `ui/app/page.tsx`
- `ui/components/service-table.tsx`
- `ui/components/status-badge.tsx`
- `ui/lib/api-client.ts`

**Estimated scope:** Medium

---

### Task 7: Add a permissions and capability view

**Description:** Add a "What can Foxhole see?" view that lists enabled integrations, read-only capabilities, confirmation-gated actions, and disabled/missing configuration. This makes the safety model visible to self-hosters.

**Acceptance criteria:**

- [x] UI shows each integration's configured status and available capabilities.
- [x] Write-capable tools clearly show Stage 1/2/3 behavior.
- [x] Secrets and raw config values are not displayed.

**Verification:**

- [x] Backend registry tests pass: `pytest tests/agent/tools/test_registry.py`
- [x] UI build passes: `pnpm build` from `ui/`.
- [x] Manual check: disabling an integration removes its capabilities from the view.

**Dependencies:** Task 5

**Files likely touched:**

- `agent/tools/registry.py`
- `agent/main.py`
- `ui/app/settings/integrations/page.tsx`
- `ui/components/settings-form.tsx`
- `tests/agent/tools/test_registry.py`

**Estimated scope:** Medium

---

### Checkpoint: Live Control Plane

- [x] Dashboard, chat, alerts, and integration settings are all backed by API data.
- [x] UI works against a configured bearer token.
- [x] Safety/capability state is visible to the user.

---

### Phase 3: Real Scheduled Diagnostics

### Task 8: Add a shared worker check envelope

**Description:** Create a structured result envelope for scheduled checks with status, severity, source, evidence, suggested actions, duration, skipped reason, and correlation ID. Add a helper that stores check results as events.

**Acceptance criteria:**

- [x] All worker tasks return the shared envelope instead of placeholder `{status, check}` payloads.
- [x] Disabled integrations return `skipped` with a clear reason.
- [x] Check results are written to Redis events when appropriate.

**Verification:**

- [x] Tests pass: `pytest tests/workers/test_tasks.py tests/agent/test_events.py`
- [x] Manual check: running one Celery task creates a readable event.

**Dependencies:** Task 1

**Files likely touched:**

- `workers/tasks.py`
- `schemas/python/events.py`
- `agent/events.py`
- `tests/workers/test_tasks.py`

**Estimated scope:** Medium

---

### Task 9: Implement Docker and storage scheduled checks

**Description:** Replace placeholder container and storage checks with deterministic diagnostics using existing Docker, Proxmox, backup, and security helpers where configured.

**Acceptance criteria:**

- [x] Container health check flags restart loops, unhealthy containers, privileged containers, host networking, and missing restart policies.
- [x] Storage check flags high usage, failed/stale backup jobs, and unavailable storage data.
- [x] Checks skip cleanly when Docker or Proxmox is disabled.

**Verification:**

- [x] Tests pass: `pytest tests/workers/test_tasks.py tests/tools/test_docker_tool.py tests/tools/test_backup_storage_health.py tests/tools/test_security_checks.py`
- [x] Manual check: mocked task output maps to warning/critical severities correctly.

**Dependencies:** Task 8

**Files likely touched:**

- `workers/tasks.py`
- `tools/docker_tool.py`
- `tools/backup_tool.py`
- `tools/security_tool.py`
- `tests/workers/test_tasks.py`

**Estimated scope:** Medium

---

### Task 10: Implement media scheduled checks

**Description:** Replace placeholder Plex and *Arr checks with deterministic diagnostics for Plex DB/log health, buffering risk, stale import queues, failed downloads, and root-folder mismatches.

**Acceptance criteria:**

- [x] Plex task reports DB lock warnings, transcode failures, and buffering risk from compact evidence.
- [x] *Arr task reports stale queue/import failures and proposed safe actions.
- [x] Checks do not request write actions; they only recommend confirmation-gated remediation.

**Verification:**

- [x] Tests pass: `pytest tests/workers/test_tasks.py tests/tools/test_plex_tool.py tests/tools/test_arr_tool.py tests/tools/test_arr_actions.py`
- [x] Manual check: fixture data produces a concise diagnostic event.

**Dependencies:** Task 8

**Files likely touched:**

- `workers/tasks.py`
- `tools/plex_tool.py`
- `tools/arr_tool.py`
- `tests/workers/test_tasks.py`

**Estimated scope:** Medium

---

### Task 11: Implement rogue MAC and DNS scheduled checks

**Description:** Replace the rogue MAC placeholder with the existing network safety constraints: configured allowed subnets only, known MAC comparison, Pi-hole recent query summaries, and Unbound health when enabled.

**Acceptance criteria:**

- [x] Public ranges are still rejected.
- [x] Unknown MAC detections create warning events with vendor/address evidence when available.
- [x] DNS degradation uses Pi-hole/Unbound summaries without exposing raw query logs by default.

**Verification:**

- [x] Tests pass: `pytest tests/workers/test_tasks.py tests/tools/test_network_tool.py tests/tools/test_network_scanning.py`
- [x] Manual check: no scan runs when `network_allowed_subnets` is empty.

**Dependencies:** Task 8

**Files likely touched:**

- `workers/tasks.py`
- `tools/network_tool.py`
- `tests/workers/test_tasks.py`

**Estimated scope:** Medium

---

### Checkpoint: Diagnostics Are Alive

- [x] Celery scheduled tasks create useful events instead of placeholders.
- [x] No worker task performs a write.
- [x] Dashboard and alerts reflect worker output.

---

### Phase 4: Durable History, Audits, and Incidents

### Task 12: Add SQLModel-backed SQLite persistence for events and check results

**Description:** Add a small SQLAlchemy/SQLModel persistence layer that stores events and scheduled check results in SQLite while keeping Redis streams as the live feed. SQLite is the default durable store; use an `agent/db/` package from the start with consolidated `session.py`, `models.py`, and `repositories.py`, leaving a clear path to optional Postgres and later per-domain repository splits.

**Acceptance criteria:**

- [x] Events survive API/worker restart.
- [x] `/events` can read from durable storage with Redis as live/cache path or fallback.
- [x] Database path is configurable and defaults to a local development path.
- [x] SQLModel/SQLAlchemy models and session helpers are isolated from API route code.
- [x] Retention settings exist for events, diagnostic runs, audits, resolved incidents, critical incidents, and pinned incidents.

**Verification:**

- [x] Tests pass: `pytest tests/agent/test_events.py tests/agent/test_settings.py`
- [x] Manual check: event inserted before restart is returned after restart.

**Dependencies:** Task 8

**Files likely touched:**

- `agent/events.py`
- `agent/settings.py`
- `agent/db/__init__.py`
- `agent/db/session.py`
- `agent/db/models.py`
- `agent/db/repositories.py`
- `schemas/python/events.py`
- `tests/agent/test_events.py`
- `pyproject.toml`
- `.env.example`

**Estimated scope:** Medium

---

### Task 13: Persist write audit records and expose safety receipts

**Description:** Move write audit records out of process memory into durable storage. Expose a read-only audit endpoint and shape write-action UI around "safety receipts" for denied, blocked, confirmed, succeeded, and failed writes. Keep approval manual for now; this durable audit layer is also the prerequisite for later pending-action and one-click approve flows.

**Acceptance criteria:**

- [x] Every attempted write creates a durable audit record.
- [x] Successful/failed tool results update the matching audit record.
- [x] API exposes recent audit records without leaking secrets or full sensitive arguments.
- [x] Confirmation-required writes are recorded with enough metadata to support future pending-action approval without replaying untrusted client state.

**Verification:**

- [x] Tests pass: `pytest tests/agent/test_write_policy.py tests/agent/test_main.py`
- [x] Manual check: denied Stage 1 write appears in audit history.

**Dependencies:** Task 12

**Files likely touched:**

- `agent/safety.py`
- `agent/main.py`
- `agent/events.py`
- `schemas/python/events.py`
- `tests/agent/test_write_policy.py`
- `tests/agent/test_main.py`

**Estimated scope:** Medium

---

### Task 13A: Add retention pruning for durable history

**Description:** Add configurable retention for durable data and a daily Celery maintenance task. Events are noisy and should expire sooner; audits are safety records and should be retained longer; incidents should keep useful operational history without unbounded growth.

**Acceptance criteria:**

- [x] Default retention is events 30 days, diagnostic runs 90 days, audits 365 days, resolved incidents 180 days, critical incidents 365 days, and pinned incidents forever.
- [x] Retention values are configurable through `FOXHOLE_*` settings and documented in `.env.example`.
- [x] A daily `foxhole.retention_prune` Celery beat task prunes only eligible records and never deletes open or pinned incidents.

**Verification:**

- [x] Tests pass: `pytest tests/agent/test_events.py tests/workers/test_tasks.py`
- [x] Manual check: seeded old records are pruned while pinned/open records remain.

**Dependencies:** Task 12, Task 13

**Files likely touched:**

- `agent/settings.py`
- `agent/db/repositories.py`
- `workers/tasks.py`
- `workers/celery_app.py`
- `tests/agent/test_events.py`
- `tests/workers/test_tasks.py`
- `.env.example`

**Estimated scope:** Small-Medium

---

### Task 14: Add incident timeline API and UI

**Description:** Group correlated events and check results into incident timelines. Start with generated incidents for repeated critical/warning events from the same source; keep manual incident editing out of scope for this update.

**Acceptance criteria:**

- [x] API can list incidents and show an incident detail timeline.
- [x] Timeline includes event timestamps, source, evidence summary, suggested action, and any write receipts.
- [x] UI has an incident detail page linked from alerts/dashboard.

**Verification:**

- [x] Tests pass: `pytest tests/agent/test_events.py tests/agent/test_main.py`
- [x] UI build passes: `pnpm build` from `ui/`.
- [x] Manual check: multiple Plex warning events appear as one incident timeline.

**Dependencies:** Task 12, Task 13

**Files likely touched:**

- `agent/main.py`
- `agent/events.py`
- `schemas/python/events.py`
- `ui/app/alerts/page.tsx`
- `ui/components/event-table.tsx`
- `tests/agent/test_events.py`

**Estimated scope:** Medium

---

### Checkpoint: History Is Trustworthy

- [x] Event and audit history survives restarts.
- [x] Write attempts produce durable safety receipts.
- [x] Incidents explain what happened over time.

---

### Phase 5: Mock Mode and Evaluation Fixtures

### Task 15: Make `FOXHOLE_MOCK_MODE=1` affect runtime tools

**Description:** Wire `agent/mock_mode.py` into tool execution so enabled mock mode returns deterministic data from fixtures instead of calling real homelab services. This supports demos, screenshots, tests, and local UI development.

**Acceptance criteria:**

- [x] Mock mode can simulate Docker, Proxmox, Plex, *Arr, Pi-hole, and event data.
- [x] Runtime tools use mock data only when explicitly enabled.
- [x] Tests prove mock mode avoids external network/service calls.

**Verification:**

- [x] Tests pass: `pytest tests/tools tests/agent/test_settings.py`
- [x] Manual check: backend can run with mock mode and no real integrations.

**Dependencies:** Task 8

**Files likely touched:**

- `agent/mock_mode.py`
- `agent/settings.py`
- `tools/*.py`
- `tests/fixtures/mock-data.json`
- `tests/tools/*.py`

**Estimated scope:** Medium

---

### Task 16: Add broken-homelab evaluation scenarios

**Description:** Add deterministic scenarios such as Plex DB locked, Sonarr import stuck, Docker restart loop, Pi-hole DNS failure, stale Proxmox backup, disk filling fast, and rogue LAN device. Each scenario should define expected findings and evidence.

**Acceptance criteria:**

- [x] At least five scenarios exist with input fixture data and expected diagnosis.
- [x] A test helper can run a scenario through diagnostic bundles without an LLM.
- [x] Failures show which expected finding/evidence was missing.

**Verification:**

- [x] Tests pass: `pytest tests/evals tests/workers/test_tasks.py`
- [x] Manual check: one scenario can drive the UI in mock mode.

**Dependencies:** Task 15

**Files likely touched:**

- `tests/fixtures/`
- `tests/evals/`
- `agent/mock_mode.py`
- `workers/tasks.py`

**Estimated scope:** Medium

---

### Checkpoint: Demo and Regression Mode

- [x] A new contributor can run Foxhole without a homelab and see realistic issues.
- [x] Diagnostic quality can regress in tests before users notice it.

---

### Phase 6: Token and Cost Control

### Task 17: Add intent-based tool loading

**Description:** Filter tool schemas per chat request using enabled integrations, lightweight intent classification, and capability metadata. The LLM should not receive every configured tool for every prompt.

**Acceptance criteria:**

- [x] Plex/media prompts only load relevant Plex, Tautulli, Docker, storage, and media tools.
- [x] Network prompts only load relevant network/security tools.
- [x] Fallback behavior remains safe when intent is unknown.

**Verification:**

- [x] Tests pass: `pytest tests/agent/test_orchestrator.py tests/agent/tools/test_registry.py`
- [x] Manual check: trace/debug output shows fewer schemas sent for targeted prompts.

**Dependencies:** Task 1, Task 7

**Files likely touched:**

- `agent/orchestrator.py`
- `agent/tools/registry.py`
- `agent/tools/base.py`
- `tests/agent/test_orchestrator.py`
- `tests/agent/tools/test_registry.py`

**Estimated scope:** Medium

---

### Task 18: Add tool output modes and raw-log guards

**Description:** Make tools support output modes such as `summary`, `diagnostic`, `raw`, and `forensic`. Default to compact summaries and require explicit user request plus policy allowance before raw logs enter the conversation.

**Acceptance criteria:**

- [x] Docker/Plex log tools default to compact extracted patterns.
- [x] Raw/forensic mode is bounded by max lines and max bytes.
- [x] Chat traces show whether raw data was withheld or summarized.

**Verification:**

- [x] Tests pass: `pytest tests/tools/test_docker_tool.py tests/tools/test_plex_tool.py tests/agent/test_orchestrator.py`
- [x] Manual check: asking for a diagnosis does not dump raw logs into the LLM context.

**Dependencies:** Task 1, Task 17

**Files likely touched:**

- `agent/tools/base.py`
- `tools/docker_tool.py`
- `tools/plex_tool.py`
- `agent/orchestrator.py`
- `tests/tools/test_docker_tool.py`
- `tests/tools/test_plex_tool.py`

**Estimated scope:** Medium

---

### Task 19: Add agent budget accounting

**Description:** Track model calls, tool calls, log lines, input/output token estimates, and estimated cost per chat run. Enforce conservative defaults and show the budget summary in responses and the UI.

**Acceptance criteria:**

- [x] Each chat response includes budget metadata.
- [x] Requests stop safely when max tool/model calls are exceeded.
- [x] UI displays tool calls, model calls, token estimates, and cost estimate when available.

**Verification:**

- [x] Tests pass: `pytest tests/agent/test_chat.py tests/agent/test_orchestrator.py`
- [x] UI build passes: `pnpm build` from `ui/`.
- [x] Manual check: budget limit produces a clear answer instead of a runaway loop.

**Dependencies:** Task 17, Task 18

**Files likely touched:**

- `agent/orchestrator.py`
- `agent/llm/client.py`
- `schemas/python/chat.py`
- `ui/app/chat/page.tsx`
- `tests/agent/test_orchestrator.py`

**Estimated scope:** Medium

---

### Checkpoint: Agent Is Controllable

- [x] Tool schemas are scoped to the request.
- [x] Raw logs are not included by default.
- [x] Users can see approximate diagnostic cost and execution budget.

---

### Phase 7: Modular Growth and Self-Hoster Integrations

### Task 20: Add capability metadata for existing integrations

**Description:** Extend tool registration with stable capability IDs such as `containers.list`, `containers.restart.confirmed`, `media.sessions.read`, `dns.queries.read`, and `security.posture.read`. Use this metadata for permissions views, intent routing, and future plugin manifests.

**Acceptance criteria:**

- [ ] Every registered tool exposes one or more capability IDs.
- [ ] Capability metadata includes read/write category and integration ownership.
- [x] Existing registry schema output remains OpenAI-compatible.

**Verification:**

- [x] Tests pass: `pytest tests/agent/tools/test_registry.py tests/agent/test_orchestrator.py`
- [x] Manual check: permissions view can render capabilities without hardcoding tool names.

**Review note:** Existing capability display is a permissions view based on integration/tool names and safety levels. The stable capability ID metadata required by this task is not implemented yet.

**Dependencies:** Task 7, Task 17

**Files likely touched:**

- `agent/tools/base.py`
- `agent/tools/registry.py`
- `tools/*.py`
- `tests/agent/tools/test_registry.py`

**Estimated scope:** Medium

---

### Task 21: Introduce an integration manifest format

**Description:** Add a lightweight manifest format for integrations that describes ID, name, version, category, required/optional config schema, exposed capabilities, tool definitions, input/output schemas, safety levels, resource URIs, event types, diagnostic bundles, and safety posture. Start by generating manifests for existing built-in integrations and shape the metadata so it can later map cleanly to MCP tools/resources without exposing an MCP server yet.

**Acceptance criteria:**

- [ ] Built-in integrations can expose manifest metadata without changing their runtime behavior.
- [ ] UI can consume manifest metadata for settings and capability display.
- [ ] Manifest format is documented enough for a future community integration guide.
- [ ] Manifest capability/resource concepts include notes for a future MCP adapter.
- [ ] Minimum stable fields are present: `id`, `name`, `version`, `category`, config schema, capabilities, tools, input/output schemas, safety levels, resource URIs, and event types.

**Verification:**

- [ ] Tests pass: `pytest tests/agent/tools/test_registry.py`
- [ ] Manual check: manifest output for Docker, Plex, Proxmox, and Pi-hole is readable.

**Dependencies:** Task 20

**Files likely touched:**

- `agent/tools/registry.py`
- `agent/tools/base.py`
- `docs/architecture.md`
- `docs/integrations/*.md`
- `tests/agent/tools/test_registry.py`

**Estimated scope:** Medium

---

### Task 22: Add the first monitoring integration slice: Uptime Kuma

**Description:** Add Uptime Kuma as the first post-core integration. Keep the slice read-only: import monitor status and recent incidents, then let Foxhole explain monitor failures by correlating them with Docker, DNS, reverse proxy, and recent events when those integrations are enabled.

**Acceptance criteria:**

- [ ] Settings support Uptime Kuma base URL and token/API credentials.
- [ ] Tool can list monitor status and recent failures.
- [ ] Worker check can create warning/critical events from failed monitors.

**Verification:**

- [ ] Tests pass: `pytest tests/tools tests/workers/test_tasks.py`
- [ ] Manual check: mock mode can show a failed monitor on the dashboard.

**Dependencies:** Task 20, Task 21

**Files likely touched:**

- `agent/settings.py`
- `tools/uptime_kuma_tool.py`
- `agent/tools/registry.py`
- `workers/tasks.py`
- `tests/tools/test_uptime_kuma_tool.py`
- `.env.example`

**Estimated scope:** Medium

---

### Task 23: Add a Homepage/Homarr-compatible status widget endpoint

**Description:** Expose a small authenticated or token-scoped JSON endpoint for existing self-hosted dashboards. It should show overall Foxhole status, warning/critical counts, latest incident, and suggested action.

**Acceptance criteria:**

- [ ] Endpoint returns compact JSON suitable for Homepage/Homarr custom widgets.
- [ ] Endpoint can be disabled or protected by a separate widget token.
- [ ] Docs include example widget configuration.

**Verification:**

- [ ] Tests pass: `pytest tests/agent/test_main.py`
- [ ] Manual check: endpoint returns useful data with mock events.

**Dependencies:** Task 5, Task 14

**Files likely touched:**

- `agent/main.py`
- `agent/settings.py`
- `docs/integrations/`
- `tests/agent/test_main.py`

**Estimated scope:** Small-Medium

---

### Task 24: Add the first reverse proxy integration slice: Caddy

**Description:** Add Caddy as the first reverse proxy integration after Uptime Kuma. Keep it read-only: parse or query Caddy configuration, list configured routes, detect upstream targets, and diagnose route/upstream mismatches without editing proxy config.

**Acceptance criteria:**

- [ ] Settings support a Caddyfile/config path and optional Caddy admin API URL.
- [ ] Tool can list routes and upstream targets from supported Caddy configuration.
- [ ] Diagnostic can flag dead upstreams, routes pointing to missing containers, and likely 502 causes.
- [ ] Manifest exposes reverse-proxy capabilities and resource URIs for future MCP mapping.

**Verification:**

- [ ] Tests pass: `pytest tests/tools tests/agent/tools/test_registry.py`
- [ ] Manual check: mock mode can show an Uptime Kuma failure correlated with a Caddy upstream mismatch.

**Dependencies:** Task 21, Task 22

**Files likely touched:**

- `agent/settings.py`
- `tools/caddy_tool.py`
- `agent/tools/registry.py`
- `tests/tools/test_caddy_tool.py`
- `tests/fixtures/mock-data.json`
- `.env.example`
- `docs/integrations/caddy.md`

**Estimated scope:** Medium

---

### Checkpoint: Community-Ready Direction

- [ ] Existing integrations have capability and manifest metadata.
- [ ] At least one new read-only integration follows the manifest pattern.
- [ ] Foxhole can surface status inside existing self-hosted dashboards.

---

## Future Integration Backlog

Prioritize integrations that help Foxhole explain existing self-hosted systems rather than replace them:

- **Infrastructure:** Proxmox Backup Server, TrueNAS/ZFS, Synology, smartctl/Scrutiny, NUT/UPS, Restic, Kopia.
- **Networking and exposure:** Caddy first, then Nginx Proxy Manager, then Traefik; Cloudflare Tunnel, Tailscale, and Headscale after route/upstream diagnostics exist.
- **Monitoring:** Gatus, Prometheus, Grafana, Netdata, Healthchecks, Loki, Grafana Alloy/OpenTelemetry Collector.
- **Automation and alerts:** Gotify, Apprise, Discord, Matrix, n8n, Node-RED, Home Assistant, MQTT.
- **Security:** Wazuh, CrowdSec, Fail2ban, Suricata, Zeek, SSH auth log review, Docker image vulnerability scanning.

Each new integration should land as a vertical slice: settings, read-only tools, tests, mock data, scheduled event generation, capability metadata, and documentation.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| UI work exposes protected endpoints without auth | High | Complete HTTP-only cookie login before wiring pages. Add explicit 401/503 states. |
| Worker tasks accidentally perform mutations | High | Keep worker checks read-only and assert no write tools are invoked in tests. |
| Raw logs overload prompts or leak sensitive data | High | Add output modes, bounded log extraction, and default summaries before more LLM features. |
| SQLite and Redis event paths diverge | Medium | Define one SQLModel-backed durable event model and write tests for both storage and retrieval paths. |
| Durable SQLite grows without bound | Medium | Ship opinionated retention defaults and a daily `foxhole.retention_prune` task. |
| Plugin architecture becomes a rewrite | Medium | Start with metadata around existing registry, then extract runtime later only if needed. |
| Too many integrations delay a usable product | Medium | Finish UI, diagnostics, persistence, mock mode, and budget controls before adding broad integration packs. |
| Auth expectations outgrow cookie login | Medium | Keep login/session handling isolated; plan OIDC/authentik/Authelia after core flows work. |

## Parallelization Opportunities

- **Safe to parallelize after Task 1:** UI auth/chat work, worker envelope design, and persistence design.
- **Safe to parallelize after Task 8:** Docker/storage checks, media checks, and network checks.
- **Safe to parallelize after Task 12:** Audit receipts and incident UI, as long as the event schema is frozen.
- **Must be sequential:** Evidence schemas before UI rendering; cookie login before protected UI pages; worker envelope before real checks; durable storage before audit/incident history; capability metadata before plugin manifests.
- **Needs coordination:** Any change to `schemas/python/chat.py`, `schemas/python/events.py`, or `agent/tools/base.py`.

## Resolved Decisions

- Durable store: SQLite is the default durable store, and the project should introduce SQLAlchemy/SQLModel now.
- SQLModel layout: use a small `agent/db/` package now, with consolidated `session.py`, `models.py`, and `repositories.py`; split by domain later.
- Browser auth: the UI should use an HTTP-only cookie set by a small login endpoint after bearer-token validation.
- Cookie profiles: local Compose uses `HttpOnly`, `Secure=False`, `SameSite=Lax`; HTTPS proxy deployments use `HttpOnly`, `Secure=True`, `SameSite=Strict`, and `__Host-foxhole_session` when possible.
- Confirmation flow: manual confirmation-token paste ships first; one-click approve comes later after durable pending actions exist.
- Retention policy: events 30 days, diagnostic runs 90 days, audits 365 days, resolved incidents 180 days, critical incidents 365 days, and pinned/open incidents are not auto-deleted.
- Next integration: Uptime Kuma is the first post-core integration slice.
- Reverse proxy order: Caddy first, then Nginx Proxy Manager, then Traefik.
- MCP: design capability and manifest metadata for MCP now, but expose an MCP server only after plugin manifests stabilize around ID, version, config schema, capabilities, tools, schemas, safety levels, resources, and events.

## Open Questions

- Should retention pruning create an export/snapshot before deleting old audit or incident records?
- Should Caddy support start with Caddyfile parsing only, the admin API only, or both in the first slice?
- Should the first MCP adapter expose only Foxhole-level diagnostic tools/resources, or also selected low-level integration tools after policy filtering?

## Verification Before Implementation

- [x] Every task has acceptance criteria.
- [x] Every task has verification steps.
- [x] Task dependencies are identified and ordered.
- [x] No planned implementation task is larger than a medium vertical slice.
- [x] Checkpoints exist after major phases.
- [ ] Human has reviewed and approved the plan before implementation starts.
