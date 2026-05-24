# Implementation Plan: Foxhole Deployment Architecture Simplification

## Overview

Foxhole currently has a capable but deployment-heavy backend architecture: Docker Compose runs FastAPI, Celery worker, Celery beat, Redis, Flower, and a Docker socket proxy, while the Next.js UI runs separately during development. The Proxmox LXC and Debian/Ubuntu systemd paths install only the FastAPI service, so they do not currently provide the same scheduled diagnostics/event behavior as Compose. This plan simplifies Foxhole toward a self-hoster-friendly default: one Foxhole container or service that serves the dashboard, API, scheduler, and durable SQLite-backed history, plus an optional Docker socket proxy when Docker diagnostics are enabled. The current Celery/Redis architecture should be preserved as an advanced distributed mode until the single-process path is proven.

## Repo Truth Summary

- `iac/compose/docker-compose.yml` currently defines `api`, `worker`, `beat`, `redis`, `flower`, and `docker-socket-proxy`.
- `workers/celery_app.py` uses Redis as both Celery broker and backend.
- `agent/events.py` stores events in SQLite first, then attempts to also write/read Redis streams; event reads can fall back to durable SQLite.
- The Next.js UI in `ui/` is not part of the Compose stack and is currently run separately with `pnpm dev`.
- The backend Dockerfile builds only the Python/FastAPI app and exposes port `8000`.
- LXC and Debian/Ubuntu installs create a hardened `homelab-agent.service` for the API only; they do not provision Redis, Celery worker, Celery beat, Flower, or the UI.
- Compose persists Redis data but does not currently mount a dedicated SQLite data directory or host config file for settings edited through the UI.
- The product is single-tenant by design, with opt-in integrations and a read-only-first safety model.

## Target Architecture

Default self-hosted architecture:

```text
Browser
  |
  v
Foxhole process/container
  |-- FastAPI API
  |-- static dashboard assets
  |-- in-process scheduler
  |-- in-memory live event fanout
  |-- SQLite durable history at /data/foxhole.db
  `-- config file at /config/foxhole.env
        |
        |-- homelab service APIs
        `-- optional Docker socket proxy
```

Advanced distributed architecture, retained only as an opt-in mode:

```text
FastAPI API
  |
  |-- Redis
  |-- Celery worker
  |-- Celery beat
  |-- optional Flower
  `-- Docker socket proxy
```

## Architecture Decisions

- **Single-process should become the default.** A homelab agent usually runs as one tenant on one host. Requiring Redis, Celery worker, Celery beat, and Flower by default is unnecessary deployment friction.
- **Do not delete Celery first.** Add a single-process mode beside the existing distributed mode, prove parity, then make it the default. This avoids breaking scheduled diagnostics while the replacement is still young.
- **SQLite is the durable source of truth.** Redis streams are useful for live/distributed behavior, but history, incidents, audits, and check results should survive restarts through SQLite.
- **Live events can be in-memory in single-process mode.** Use an in-process broadcaster only for immediate UI push. Missed events should be recoverable from SQLite.
- **Dashboard should be production-served by Foxhole.** The UI should not require a separate Node deployment for the default install. Build it into static assets and serve it from FastAPI if static export works cleanly.
- **Docker socket proxy remains separate and optional.** A second container is acceptable when Docker diagnostics are enabled because it enforces a security boundary around `/var/run/docker.sock`.
- **Flower should be debug-only.** It should not run in the default Compose stack.
- **Configuration needs a mounted home.** UI-written settings must persist on the host, not inside an ephemeral container layer.

## Dependency Graph

```text
Compose persistence fixes
  |
  |-- config file path abstraction
  |     |
  |     `-- UI settings persistence works in containers/systemd
  |
  |-- static UI build feasibility
  |     |
  |     `-- FastAPI serves dashboard
  |
  |-- scheduler abstraction
  |     |
  |     |-- APScheduler/in-process scheduler
  |     |-- Redis optional readiness
  |     `-- Compose single-process profile
  |
  `-- docs and release image cleanup
        |
        `-- one-command self-host install
```

## Task List

### Phase 1: Immediate Deployment Correctness

### Task 1: Persist SQLite data in Docker Compose

**Description:** Update the Compose deployment so durable SQLite state is written to a host-mounted data directory. This prevents event history, audits, incidents, and check results from disappearing when the API container is recreated.

**Acceptance criteria:**

- [ ] Compose creates or uses a host `./data` directory.
- [ ] API, worker, and beat agree on `FOXHOLE_DATABASE_PATH=/app/data/foxhole.db`.
- [ ] The README and Docker Compose deployment docs identify `./data/foxhole.db` as state that should be backed up.

**Verification:**

- [ ] Tests pass: `python -m pytest tests/agent/test_events.py tests/agent/test_main.py`
- [ ] Compose config validates: `docker compose -f iac/compose/docker-compose.yml config`
- [ ] Manual check: event inserted before `docker compose up --force-recreate` remains visible after restart.

**Dependencies:** None

**Files likely touched:**

- `iac/compose/docker-compose.yml`
- `docs/deployment/docker-compose.md`
- `README.md`

**Estimated scope:** Small

---

### Task 2: Persist UI-editable configuration on the host

**Description:** The settings UI calls `PATCH /settings`, and `agent.settings.update_env_file()` currently writes to `.env` by default. In Compose, `env_file` loads `iac/compose/.env`, but the container does not mount that file at `/app/.env`. Add a real configurable config path or mount so UI changes persist across container recreation.

**Acceptance criteria:**

- [ ] Settings updates write to a host-mounted config file or config directory.
- [ ] The config write path is configurable, not hardcoded to an ephemeral container `.env`.
- [ ] Compose maps the host config location into the API container.
- [ ] Systemd/LXC still use `/etc/homelab-agent/foxhole.env`.

**Verification:**

- [ ] Tests pass: `python -m pytest tests/agent/test_settings.py tests/agent/test_main.py`
- [ ] Manual check: change an integration setting through the UI/API, recreate the container, and confirm the setting remains.

**Dependencies:** Task 1

**Files likely touched:**

- `agent/settings.py`
- `agent/main.py`
- `tests/agent/test_settings.py`
- `tests/agent/test_main.py`
- `iac/compose/docker-compose.yml`
- `.env.example`
- `iac/compose/.env.example`
- `docs/deployment/docker-compose.md`

**Estimated scope:** Medium

---

### Task 3: Remove Flower from the default Compose path

**Description:** Flower is useful for debugging Celery, but it is not part of a normal self-hosted agent runtime. Move it behind a Compose profile so default Compose runs fewer services.

**Acceptance criteria:**

- [ ] `docker compose -f iac/compose/docker-compose.yml up` does not start Flower.
- [ ] `docker compose --profile debug ... up flower` starts Flower when requested.
- [ ] Deployment docs describe Flower as optional/debug-only.

**Verification:**

- [ ] Compose config validates without the debug profile.
- [ ] Compose config validates with `--profile debug`.
- [ ] Manual check: default `docker compose ps` excludes Flower.

**Dependencies:** None

**Files likely touched:**

- `iac/compose/docker-compose.yml`
- `docs/deployment/docker-compose.md`
- `README.md`

**Estimated scope:** Small

---

### Checkpoint: Compose Is Not Losing User Data

- [ ] SQLite history survives container recreation.
- [ ] UI/API settings changes survive container recreation.
- [ ] Default Compose no longer starts Flower.
- [ ] Existing tests pass.

---

### Phase 2: Ship The UI With The App

### Task 4: Make the UI API client support same-origin deployment

**Description:** The UI currently defaults to `http://localhost:8000`. For a static dashboard served by FastAPI, the browser should use same-origin API calls by default, while still allowing `NEXT_PUBLIC_API_URL` for separate UI deployments.

**Acceptance criteria:**

- [ ] UI API client defaults to relative API URLs when no `NEXT_PUBLIC_API_URL` is set.
- [ ] Existing local development still works with `NEXT_PUBLIC_API_URL` or documented proxy behavior.
- [ ] Auth cookies work for same-origin dashboard/API access.

**Verification:**

- [ ] UI lint/build passes: `pnpm lint`, `pnpm build`
- [ ] Manual check: same-origin dashboard can call `/readyz`, `/capabilities`, and `/dashboard/summary`.

**Dependencies:** None

**Files likely touched:**

- `ui/lib/api-client.ts`
- `ui/README.md`
- `README.md`

**Estimated scope:** Small

---

### Task 5: Prove or adapt Next.js static export

**Description:** Determine whether the current App Router UI can be statically exported. The dynamic incident route and any browser-only fetch behavior may need small changes. The goal is a static `out/` directory that can be copied into the backend image.

**Acceptance criteria:**

- [ ] `next.config.ts` supports a production static export path, or a documented blocker is removed.
- [ ] Dynamic incident route works under static hosting, or incident detail is refactored to a client-side route that can be statically exported.
- [ ] Build output can be copied into the Python image without Node.js runtime.

**Verification:**

- [ ] UI export/build command succeeds.
- [ ] Manual check: dashboard, settings, alerts, chat, and incident detail routes render under static hosting.

**Dependencies:** Task 4

**Files likely touched:**

- `ui/next.config.ts`
- `ui/app/incidents/[id]/page.tsx`
- `ui/package.json`
- `ui/README.md`

**Estimated scope:** Medium

---

### Task 6: Serve static UI assets from FastAPI

**Description:** Mount the exported dashboard assets in FastAPI so one backend process can serve both the UI and API. API routes must continue to win over the static catch-all.

**Acceptance criteria:**

- [ ] FastAPI serves the dashboard at `/`.
- [ ] API endpoints continue to work at their existing paths.
- [ ] Unknown UI routes fall back to the static app where appropriate.
- [ ] Docker image includes the exported UI assets.

**Verification:**

- [ ] Backend tests pass: `python -m pytest tests/agent/test_main.py`
- [ ] UI build/export passes.
- [ ] Docker image builds.
- [ ] Manual check: `http://localhost:8000/` loads the dashboard from the backend container.

**Dependencies:** Task 5

**Files likely touched:**

- `agent/main.py`
- `Dockerfile`
- `tests/agent/test_main.py`
- `README.md`
- `docs/deployment/docker-compose.md`

**Estimated scope:** Medium

---

### Task 7: Add a full-stack default Compose path

**Description:** Once FastAPI serves the UI, update Compose and documentation so the default user path is a single Foxhole service plus optional Docker socket proxy. This task should not remove Celery yet; it should introduce the new full-stack app shape while the current distributed stack still exists.

**Acceptance criteria:**

- [ ] Default Compose exposes one user-facing Foxhole port.
- [ ] The UI is available without running `pnpm dev`.
- [ ] Redis/Celery services are either still present for the old mode or moved toward a profile.
- [ ] README quick start shows a real self-hosted dashboard URL.

**Verification:**

- [ ] Compose config validates.
- [ ] Docker image builds.
- [ ] Manual check: `docker compose up --build` loads dashboard and API health.

**Dependencies:** Task 6

**Files likely touched:**

- `iac/compose/docker-compose.yml`
- `Dockerfile`
- `README.md`
- `docs/deployment/docker-compose.md`

**Estimated scope:** Medium

---

### Checkpoint: One App Serves API And Dashboard

- [ ] Dashboard loads from the Foxhole backend container.
- [ ] No separate Node.js process is required for normal deployment.
- [ ] Existing API, auth cookie, and integration settings flows still work.
- [ ] Docker and systemd docs clearly distinguish dev UI from production UI.

---

### Phase 3: Single-Process Runtime Mode

### Task 8: Extract scheduled checks behind a scheduler-neutral interface

**Description:** Scheduled diagnostics currently live as Celery tasks. Extract the check execution logic into plain callable functions that both Celery and an in-process scheduler can use. Avoid changing behavior in this task.

**Acceptance criteria:**

- [ ] Existing Celery tasks become thin wrappers around scheduler-neutral functions.
- [ ] Check names, source values, result envelopes, and stored events stay unchanged.
- [ ] Tests continue to validate scheduled check outputs.

**Verification:**

- [ ] Tests pass: `python -m pytest tests/workers/test_tasks.py tests/agent/test_events.py`
- [ ] Manual check: one Celery task still stores a scheduled check event.

**Dependencies:** None

**Files likely touched:**

- `workers/tasks.py`
- `tests/workers/test_tasks.py`

**Estimated scope:** Medium

---

### Task 9: Add an in-process scheduler

**Description:** Add a FastAPI lifespan-managed scheduler for single-process deployments. APScheduler is the likely fit. The scheduler should run the same diagnostics as Celery beat, with conservative concurrency and timeout behavior.

**Acceptance criteria:**

- [ ] `FOXHOLE_RUNTIME_MODE=single` starts an in-process scheduler with the current check cadence.
- [ ] Blocking diagnostic work runs outside the event loop where needed.
- [ ] A check cannot overlap with itself if it runs long.
- [ ] Scheduler shutdown is clean on API shutdown.

**Verification:**

- [ ] Tests cover scheduler registration without waiting real minutes.
- [ ] Tests cover disabled scheduler mode.
- [ ] Manual check: a short test interval stores a scheduled check event in SQLite.

**Dependencies:** Task 8

**Files likely touched:**

- `agent/main.py`
- `agent/settings.py`
- `agent/scheduler.py`
- `tests/agent/test_scheduler.py`
- `pyproject.toml`

**Estimated scope:** Medium

---

### Task 10: Make Redis optional in single-process mode

**Description:** In single-process mode, Redis should not be required for readiness or event retrieval. SQLite should be enough for durable history, and in-memory fanout should handle live UI updates.

**Acceptance criteria:**

- [ ] `/readyz` does not fail because Redis is absent in `single` mode.
- [ ] `/events` works from SQLite when Redis is absent.
- [ ] Redis remains required or checked in `distributed` mode.
- [ ] Error logs do not spam Redis connection failures in single mode.

**Verification:**

- [ ] Tests pass: `python -m pytest tests/agent/test_main.py tests/agent/test_events.py`
- [ ] Manual check: run API with no Redis and confirm readiness/events work in single mode.

**Dependencies:** Task 9

**Files likely touched:**

- `agent/main.py`
- `agent/events.py`
- `agent/settings.py`
- `tests/agent/test_main.py`
- `tests/agent/test_events.py`

**Estimated scope:** Medium

---

### Task 11: Add in-memory event fanout for live UI behavior

**Description:** Replace Redis as the default live-event fanout mechanism in single-process mode. Keep SQLite as the durable source of truth and Redis as the distributed-mode fanout if retained.

**Acceptance criteria:**

- [ ] `store_event()` stores to SQLite and broadcasts to in-memory subscribers in single mode.
- [ ] Event consumers can reconnect and recover recent history from SQLite.
- [ ] Redis event stream behavior remains available in distributed mode.

**Verification:**

- [ ] Tests cover in-memory broadcast and SQLite fallback.
- [ ] Tests cover Redis-disabled event storage.
- [ ] Manual check: UI/event polling or stream updates after a scheduled check.

**Dependencies:** Task 10

**Files likely touched:**

- `agent/events.py`
- `agent/event_bus.py`
- `tests/agent/test_events.py`

**Estimated scope:** Medium

---

### Task 12: Move Celery/Redis services into a distributed Compose profile

**Description:** Once single-process scheduling works, make it the default Compose mode. Preserve the existing Celery/Redis stack behind a `distributed` profile for advanced installs and future scale-out.

**Acceptance criteria:**

- [ ] Default Compose starts Foxhole and optional Docker socket proxy only.
- [ ] `--profile distributed` starts Redis, worker, and beat.
- [ ] `--profile debug` starts Flower.
- [ ] Docs explain when distributed mode is useful.

**Verification:**

- [ ] Compose config validates for default, distributed, and debug profiles.
- [ ] Manual check: default mode runs scheduled checks without Redis.
- [ ] Manual check: distributed mode still runs Celery tasks.

**Dependencies:** Task 11

**Files likely touched:**

- `iac/compose/docker-compose.yml`
- `docs/deployment/docker-compose.md`
- `README.md`

**Estimated scope:** Medium

---

### Checkpoint: Redis/Celery Are No Longer Required By Default

- [ ] One Foxhole app container can serve UI/API and run scheduled checks.
- [ ] SQLite persists history.
- [ ] Redis/Celery remain available only when explicitly enabled.
- [ ] LXC/systemd deployments have a complete scheduler story without extra services.

---

### Phase 4: LXC And Systemd Parity

### Task 13: Update LXC and Debian/Ubuntu docs for single-process parity

**Description:** After single-process mode exists, the LXC and systemd deployment docs should no longer be second-class. They should explain that the systemd service serves the API, dashboard, and scheduler without Redis/Celery by default.

**Acceptance criteria:**

- [ ] LXC docs describe the complete runtime included in `homelab-agent.service`.
- [ ] Debian/Ubuntu docs describe the complete runtime included in `homelab-agent.service`.
- [ ] Redis/Celery are described as optional distributed-mode additions, not required defaults.

**Verification:**

- [ ] Manual doc review against actual service file and settings.
- [ ] Install script dry-run or shellcheck where available.

**Dependencies:** Task 12

**Files likely touched:**

- `docs/deployment/proxmox-lxc.md`
- `docs/deployment/debian-ubuntu.md`
- `iac/lxc/systemd/homelab-agent.service`
- `iac/ansible/roles/agent/tasks/main.yml`

**Estimated scope:** Small

---

### Task 14: Add backup and restore documentation

**Description:** Self-hosters expect clear backup semantics. Document exactly which paths contain durable data and secrets for Compose, LXC, and systemd.

**Acceptance criteria:**

- [ ] Compose backup docs cover `./data` and `./config`.
- [ ] LXC/systemd backup docs cover `/etc/homelab-agent/foxhole.env` and the configured SQLite database path.
- [ ] Restore procedure is documented for each deployment path.

**Verification:**

- [ ] Manual check: commands are copy-pasteable and path names match repo config.

**Dependencies:** Task 1, Task 2, Task 13

**Files likely touched:**

- `docs/deployment/docker-compose.md`
- `docs/deployment/proxmox-lxc.md`
- `docs/deployment/debian-ubuntu.md`
- `README.md`

**Estimated scope:** Small

---

### Task 15: Add reverse proxy examples

**Description:** Provide copy-paste examples for exposing Foxhole behind Caddy or another reverse proxy. Include cookie/security settings relevant to browser auth.

**Acceptance criteria:**

- [ ] Caddy example proxies the unified Foxhole app.
- [ ] Docs mention `FOXHOLE_SESSION_COOKIE_SECURE`, SameSite behavior, and allowed origins if separate UI/API mode is used.
- [ ] Examples do not expose Docker socket proxy or Redis.

**Verification:**

- [ ] Manual check: reverse proxy example routes `/`, `/healthz`, and API endpoints to Foxhole.

**Dependencies:** Task 6

**Files likely touched:**

- `docs/deployment/docker-compose.md`
- `docs/integrations/caddy.md`
- `README.md`

**Estimated scope:** Small

---

### Checkpoint: All Deployment Paths Tell The Same Story

- [ ] Compose, LXC, and Debian/Ubuntu docs describe equivalent default runtime behavior.
- [ ] Backup/restore paths are clear.
- [ ] Reverse proxy deployment is documented.

---

### Phase 5: Release And One-Command Self-Host

### Task 16: Publish and document GHCR images

**Description:** The release workflow can publish images on tags, but the README currently avoids claiming a published image. Once a release is tagged and available, update Compose examples to support image-based deployment instead of local builds.

**Acceptance criteria:**

- [ ] A tagged GHCR image exists.
- [ ] Compose supports `image: ghcr.io/...` for normal users.
- [ ] Local build remains documented for contributors.
- [ ] README no longer says there is no published image after images actually exist.

**Verification:**

- [ ] GitHub Actions release workflow succeeds.
- [ ] Manual check: `docker pull ghcr.io/<owner>/<repo>:<tag>` works.
- [ ] Manual check: image-based Compose starts Foxhole.

**Dependencies:** Task 12

**Files likely touched:**

- `.github/workflows/release.yml`
- `iac/compose/docker-compose.yml`
- `docs/release.md`
- `README.md`

**Estimated scope:** Medium

---

### Task 17: Create a minimal one-command Compose example

**Description:** Provide a small Compose example that looks like what self-hosters expect: one Foxhole service, optional socket proxy, one data volume, one config volume, one port.

**Acceptance criteria:**

- [ ] Minimal Compose example starts the full app.
- [ ] Only required first-run variable is the API/admin token.
- [ ] Optional Docker socket proxy is included with read-only defaults.
- [ ] Full distributed Compose remains available separately.

**Verification:**

- [ ] Compose config validates.
- [ ] Manual check: fresh clone or copied Compose example starts Foxhole.
- [ ] Manual check: dashboard loads and can configure integrations.

**Dependencies:** Task 16

**Files likely touched:**

- `iac/compose/docker-compose.yml`
- `iac/compose/docker-compose.distributed.yml`
- `docs/deployment/docker-compose.md`
- `README.md`

**Estimated scope:** Medium

---

### Task 18: Clean up release and upgrade docs

**Description:** `docs/release.md` currently references `RTK poetry install`, but the repo uses a `pyproject.toml`/pip install path. Update release/upgrade docs to match the actual packaging and deployment modes.

**Acceptance criteria:**

- [ ] Release docs use current install commands.
- [ ] Upgrade docs cover Compose image upgrades and source/systemd upgrades.
- [ ] Rollback docs identify the data/config directories that should not be deleted.

**Verification:**

- [ ] Manual doc review against Dockerfile, Compose, LXC, and Ansible paths.

**Dependencies:** Task 16

**Files likely touched:**

- `docs/release.md`
- `README.md`
- `docs/deployment/*.md`

**Estimated scope:** Small

---

### Checkpoint: One-Command Self-Host

- [ ] Published image exists.
- [ ] Minimal Compose file starts the full app.
- [ ] Dashboard, API, scheduler, SQLite history, and config persistence work by default.
- [ ] Docker diagnostics require only the optional socket proxy.
- [ ] Distributed mode remains documented for advanced users.

## Ideas Assessment

| Idea | Verdict | Rationale |
| --- | --- | --- |
| Replace Celery/Redis with APScheduler | Best medium-term simplification | Correct for single-tenant homelabs, but should be introduced beside Celery first. |
| Serve static UI from FastAPI | Best deployment UX improvement | Eliminates separate Node deployment. Needs static export validation first. |
| Add SQLite persistence to Compose | Must do immediately | Current Compose risks losing durable history on container recreation. |
| Add UI to Compose | Good short-term fallback | Useful if static serving takes longer, but less ideal than one app container. |
| Consolidate env vars | Good, depends on config persistence | UI-first config only works if config writes survive container recreation. |
| Remove Redis immediately | Too risky | Redis is still wired into Celery, readiness, and event streams. Make it optional after scheduler/event refactor. |
| Use FastAPI BackgroundTasks as scheduler | Does not fit | BackgroundTasks are request-adjacent, not a recurring scheduler. |
| Keep Flower by default | Does not make sense | Debug tool only; adds noise and another exposed port. |

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Duplicate scheduled jobs if multiple API workers run | High | Document one worker in single mode; add scheduler locking; use distributed mode for multi-worker installs. |
| Static export breaks dynamic incident pages | Medium | Validate export early; refactor incident detail to client-side data fetch if needed. |
| UI settings write to the wrong config file | High | Add explicit config path setting and tests before relying on UI-first config. |
| Removing Redis breaks event behavior | Medium | Make SQLite the read path first; add in-memory broadcast; keep Redis in distributed mode. |
| Long diagnostics block the API loop | High | Run blocking checks in threadpool/executor with per-check timeouts. |
| Docker socket proxy security regresses during simplification | High | Keep proxy as separate optional service; default `POST=0`; keep Stage 2 override separate. |
| Two runtime modes increase maintenance | Medium | Keep shared scheduler-neutral check functions; Celery wrappers and APScheduler jobs call the same code. |
| Published image claims outpace reality | Medium | Update README only after GHCR images are actually published and tested. |

## Open Questions

- Should the default exposed port stay `8000`, or should the all-in-one app expose `8080` or `3000` for dashboard familiarity?
- Should Compose keep distributed services in the same file behind profiles, or split into `docker-compose.yml` and `docker-compose.distributed.yml`?
- Should config persistence use mounted `.env`, mounted `/config/foxhole.env`, or a small SQLite settings table for non-secret values?
- Should the first-run setup UI be part of this plan, or a separate phase after config persistence is reliable?
- Is APScheduler the preferred dependency, or should the project use a smaller custom scheduler loop for the limited current check cadence?

## Parallelization Opportunities

- **Safe to parallelize after Task 2:** Documentation updates, Flower profile cleanup, and UI same-origin API client work.
- **Safe to parallelize after Task 5:** FastAPI static serving and Dockerfile packaging work, if the static export contract is stable.
- **Safe to parallelize after Task 8:** Scheduler tests and Redis-optional event tests, as long as the scheduler-neutral check interface is frozen.
- **Must be sequential:** Config persistence before UI-first setup claims; scheduler abstraction before APScheduler; Redis optionality before removing Redis from default Compose.
- **Needs coordination:** Any change to `agent/events.py`, `agent/settings.py`, `Dockerfile`, or Compose profiles.

## Verification Before Implementation

- [ ] Every task has acceptance criteria.
- [ ] Every task has a verification step.
- [ ] Task dependencies are identified and ordered.
- [ ] No task intentionally mixes UI packaging, scheduler behavior, and persistence changes in one slice.
- [ ] Checkpoints exist between major phases.
- [ ] Human has reviewed and approved the plan before implementation starts.
