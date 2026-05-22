---
name: secureli-modernization-plan
description: Implementation plan derived from spec-driven-development (seCureLI MVP). Use alongside planning-and-task-breakdown.md when executing milestones.
related_spec: .cursor/rules/spec-driven-development.md (section “Spec: seCureLI modernization MVP (2026)”)
---

# Implementation Plan: seCureLI modernization MVP (2026)

Derived from **`spec-driven-development.md`** (“Spec: seCureLI modernization MVP (2026)”): same success criteria, boundaries, and testing strategy. Methodology follows **`planning-and-task-breakdown.md`**.

## Overview

Deliver **Python 3.12 readiness**, **Pydantic v2**, **machine-readable scan output** (JSON then SARIF), **`init --dry-run`**, and **`doctor`**, without changing default telemetry or rewriting the Rust-free architecture. Each phase ends in a branch state where **`poetry run poe test`** can still pass.

## Dependency graph

```
dependency-injector + python range (pyproject)
         │
         ├── CI jobs (3.12) ─────────────────────┐
         │                                       │
├── Pydantic v2 + pydantic-settings ──────────┤
         │                                       │
         └── ScanFailure / ScanResult stable ──┤
                     │                           │
                     ├── scan_output (JSON)     │
                     │       │                   │
                     │       └── SARIF builders │
                     │               │           │
                     └── ScanAction + main.py ──┴── Typer --format
```

`init --dry-run` and `doctor` are **parallelizable** after foundation (no hard dependency on formatters), but sequencing them after scan work reduces context switching on `main.py`.

## Architecture decisions

- **Formatters are pure functions** in `secureli/modules/shared/scan_output/` (or equivalent); **no I/O**. Input: `ScanResult`, `list[ScanFailure]`, optional raw `output` string.
- **`--format` default `text`**: preserves current echo/print behavior; machine formats go to a **single documented stream** (prefer stdout for JSON/SARIF for CI piping).
- **Dry-run threads a boolean** into `initialize_repo` (and Typer `--dry-run`); asserts no writes under `.secureli/` and no destructive root pre-commit migration in dry-run mode.
- **Doctor**: new `DoctorAction` + container provider; read-only subprocess/file checks (`pre-commit --version`, config readability).

---

## Phase 1: Foundation — runtime + modeling

### Task 1: Python 3.12 + dependency-injector

**Description:** Widen Poetry `python` constraint to include **3.12** using a **`dependency-injector` resolution** aligned with upstream (released wheel and/or guarded git pin per repo comments around ets-labs/python-dependency-injector#765). Refresh lockfile.

**Acceptance criteria:**

- [ ] `pyproject.toml` documents supported Python including **3.12**.
- [ ] `poetry install` succeeds on **3.12** locally (or documented CI-only verification if local unavailable).
- [ ] No loosening of default telemetry (`scan` publish default stays **never**).

**Verification:**

- [ ] Tests: `poetry run pytest` (or **`poe test`** after Task 3 partial if needed).
- [ ] Manual: `python --version` 3.12 + `secureli --version`.

**Dependencies:** None  

**Files likely touched:**

- `pyproject.toml`
- `poetry.lock`
- Possibly `Dockerfile_*` / docs if versions pinned

**Estimated scope:** Medium (S–M)

---

### Task 2: Pydantic v2 — models and settings split

**Description:** Migrate **`pydantic ^1`** to **v2**; move **`Settings`** to **`pydantic-settings`**; update **`secureli_yaml_settings`** + `Settings.Config` patterns to v2 equivalents. Touch **`ScanResult` / `ScanFailure`** and other `BaseModel` call sites (`.dict()` → `.model_dump()` where applicable).

**Acceptance criteria:**

- [ ] No remaining v1-only patterns that break at import time on v2.
- [ ] `.secureli.yaml` / env loading behavior preserved (parity checklist in PR body per spec).
- [ ] All existing pytest modules import and run.

**Verification:**

- [ ] `poetry run poe coverage` (or `pytest` + coverage as in CI).
- [ ] Grep for deprecated patterns (`__config__`, `.dict(` on models) and fix or ticket.

**Dependencies:** Task 1 (or parallel if 3.12 delayed — but prefer 1 first to avoid double CI churn)

**Files likely touched:**

- `secureli/settings.py`
- `secureli/modules/shared/models/**/*.py` (many)
- `secureli/container.py` (if provider types change)
- `tests/**/*.py` (fixtures, `.dict` assertions)

**Estimated scope:** Large → **split across two PRs or sub-PRs** if needed: (2a) shared models + scan/settings, (2b) remaining modules + tests.

---

### Task 3: CI — exercise 3.12 on build & test

**Description:** Extend **`.github/workflows/build_and_test.yml`** with a **3.12** job or **matrix** (Linux minimum; Windows optional follow-up). Update **`smoke_testing.yml`** comments / versions when 3.12 is validated.

**Acceptance criteria:**

- [ ] GHA runs automated tests on **Python 3.12** for this repo.
- [ ] **3.9** (or current floor) still runs so regressions on older supported versions show up.

**Verification:**

- [ ] PR with workflow change triggers green workflow.
- [ ] Document matrix choice under spec open questions.

**Dependencies:** Tasks 1–2 substantially complete  

**Files likely touched:**

- `.github/workflows/build_and_test.yml`
- Possibly `.github/workflows/smoke_testing.yml`

**Estimated scope:** Small

---

## Checkpoint: Foundation

- [ ] `poetry run poe test` passes locally on **3.12** branch state.
- [ ] Coverage run completes; no unexplained drops.
- [ ] Human OK to proceed to formatters.

---

## Phase 2: Machine-readable scan output

### Task 4: JSON formatter module + unit tests

**Description:** Add **`secureli.modules.shared.scan_output`** (name per spec): build **JSON-serializable** payload from **`ScanResult`** / **`ScanFailure`** (hooks + custom paths represented uniformly). Include **`schema_version`** (or `version`) field for MVP-stable output.

**Acceptance criteria:**

- [ ] Valid JSON for **success**, **failure**, **empty failures** (`json.loads`).
- [ ] Uses **`ScanFailure`**: `repo`, `id`, `file`, `exitCode`.

**Verification:**

- [ ] Unit tests under `tests/modules/shared/scan_output/` (new).
- [ ] Golden or snapshot for one failure payload (`tests/fixtures/` optional).

**Dependencies:** Task 2  

**Files likely touched:**

- `secureli/modules/shared/scan_output/*.py` (new)
- `tests/modules/shared/scan_output/*.py` (new)

**Estimated scope:** Small–Medium

---

### Task 5: Wire `--format` for `scan` (text | json)

**Description:** Extend Typer **`scan`** with **`ScanOutputFormat`** (or `Literal`/`Enum`): default **`text`** (current behavior). **`ScanAction`** after merge chooses echo vs **`json.dumps`** to stdout; on failures still **`sys.exit(ExitCode.SCAN_ISSUES_DETECTED)`**.

**Acceptance criteria:**

- [ ] `secureli scan --format json` produces parseable JSON and non-zero exit on failures.
- [ ] Existing **`text`** behavior unchanged for consumers.
- [ ] **`test_main`** + **`test_scan_action`** updated for kwargs / assertions.

**Verification:**

- [ ] **`CliRunner`** tests for `--format json` plumbing.
- [ ] **`pytest.raises(SystemExit)`** for failed scan + JSON path.

**Dependencies:** Task 4  

**Files likely touched:**

- `secureli/main.py`
- `secureli/actions/scan.py`
- `secureli/container.py` (optional inject helper)
- `tests/application/test_main.py`
- `tests/actions/test_scan_action.py`

**Estimated scope:** Medium

---

### Task 6: SARIF formatter + `--format sarif`

**Description:** Implement minimal **SARIF 2.1.0** `dict` from same inputs as JSON; document gaps vs GitHub Advanced Security in README. Add golden test (sorted keys acceptable).

**Acceptance criteria:**

- [ ] When failures exist: at least **`runs`**, **`results`**, **`rules`** as needed for minimal validity; **`ruleId`** strategy documented (see spec open questions).
- [ ] Exit code behavior matches Task 5.

**Verification:**

- [ ] Unit + integration-style test with fixture failures.
- [ ] Optional: validate with external SARIF validator if low effort.

**Dependencies:** Task 5  

**Files likely touched:**

- `secureli/modules/shared/scan_output/*` (SARIF builder)
- `tests/modules/shared/scan_output/*`
- `README.md` (limitation blurb)

**Estimated scope:** Medium

---

## Checkpoint: Scan formats

- [ ] Default `text` unchanged in manual smoke.
- [ ] JSON + SARIF covered by tests + `poe test` green.

---

## Phase 3: Safer init

### Task 7: `init --dry-run`

**Description:** Add **`dry_run: bool`** to **`InitializerAction.initialize_repo`** (and Typer flag). Reuse planning logic; **skip all writes** under **`.secureli/`** and skip destructive root pre-commit migration in dry-run; print human-readable plan (bullet list acceptable for MVP).

**Acceptance criteria:**

- [ ] No writes to `.secureli/.pre-commit-config.yaml`, `.secureli.yaml`, `repo-config.yaml`, logs (see spec).
- [ ] **`CliRunner`** passes **`--dry-run`** into initializer.
- [ ] Normal **`init`** unchanged when flag absent.

**Verification:**

- [ ] `tests/actions/test_initializer_action.py` with mocks/patches proving no write.
- [ ] `tests/application/test_main.py` for flag forwarding.

**Dependencies:** Task 2 (stable models/settings)  

**Files likely touched:**

- `secureli/actions/initializer.py`
- `secureli/main.py`
- `tests/actions/test_initializer_action.py`
- `tests/application/test_main.py`

**Estimated scope:** Medium

---

## Phase 4: Doctor + documentation

### Task 8: `secureli doctor`

**Description:** New **`DoctorAction`** (read-only): checks e.g. Python version vs `pyproject` range, `pre-commit` on PATH, presence/readability of **`.secureli/.pre-commit-config.yaml`** when expected. Wire **`container`** + Typer command. Exit **0** pass, **non-zero** with actionable message on failure.

**Acceptance criteria:**

- [ ] Command registered and discoverable in `--help`.
- [ ] Tests for pass + representative failure branches (mock `shutil.which` / subprocess).

**Verification:**

- [ ] New `tests/actions/test_doctor_action.py`
- [ ] `test_main.py` invokes `doctor`

**Dependencies:** Task 1 helpful for version check semantics; can start after Checkpoint Foundation  

**Files likely touched:**

- `secureli/actions/doctor.py` (new)
- `secureli/container.py`
- `secureli/main.py`
- `tests/actions/test_doctor_action.py`
- `tests/application/test_main.py`

**Estimated scope:** Medium

---

### Task 9: README + CI snippet

**Description:** Document **`--format`**, **`init --dry-run`**, **`doctor`**; add minimal **GitHub Actions** YAML snippet using **`secureli scan --format json`** (SARIF one-liner optional).

**Acceptance criteria:**

- [ ] Matches spec success criterion 6.

**Verification:**

- [ ] Human review README section.

**Dependencies:** Tasks 5–8 as features land  

**Files likely touched:**

- `README.md`

**Estimated scope:** Small

---

## Checkpoint: MVP complete

- [ ] Spec **success criteria 1–6** satisfied or explicitly deferred with issue links.
- [ ] `poetry run poe test` + **`poe e2e`** (if feasible) green.
- [ ] Open questions in spec resolved or tracked in GitHub issues.

---

## Phase 5: Recommended follow-ons (high leverage)

These tasks extend reliability and consumer contracts beyond the MVP; sequence independently unless noted.

### Task 10: Clean-clone CI job + `poe e2e`

**Description:** Add a workflow job (or scheduled workflow) that runs **`poe test`** / **`poe e2e`** from a **clean checkout** without relying on workspace-local `.secureli` drift from **`poe test`**’s self-`init`. Mitigates masked regressions noted in risks.

**Acceptance criteria:**

- [ ] CI runs **`poe e2e`** (and optionally **`poe test`**) on a fresh clone context (e.g. ephemeral working directory / job isolation).
- [ ] Failure surfaces clearly when init/scan e2e breaks independent of contributor laptops.

**Verification:**

- [ ] Green workflow on **`main`** (or equivalent) after merge.
- [ ] Contributor doc blurb when local vs CI divergence is expected.

**Dependencies:** Checkpoint MVP complete; builds on Task 3 CI patterns  

**Files likely touched:**

- `.github/workflows/*.yml`
- `CONTRIBUTING.md` or `README.md` (short note, optional)

**Estimated scope:** Small–Medium

---

### Task 11: `pydantic-settings` — env / YAML contract tests

**Description:** Dedicated tests for **`Settings`** / **`secureli_yaml_settings`**: env vars, optional secrets source, and `.secureli.yaml` merge order match v1 parity and documented behavior (no dotenv unless explicitly reintroduced).

**Acceptance criteria:**

- [ ] Contract tests cover representative env + yaml combinations (init-time vs file loads as designed).
- [ ] Regressions caught when `BaseSettings` sources or field renames change.

**Verification:**

- [ ] `pytest` module (e.g. `tests/application/` or `tests/settings/`) with focused cases; no network.

**Dependencies:** Task 2  

**Files likely touched:**

- `tests/application/test_settings.py` (extend) or new `tests/**/test_settings_contracts.py`
- `secureli/settings.py` (only if tests expose real bugs)

**Estimated scope:** Small

---

### Task 12: JSON Schema + `schema_version` policy for `scan --format json`

**Description:** Publish a **JSON Schema** (or documented OpenAPI-style fragment) for the scan JSON payload; define **version bump rules** for `schema_version` (when fields change, when to increment). Ship schema in-repo (`schemas/` or docs) and reference from README.

**Acceptance criteria:**

- [ ] Artifact checked in or generated in build; consumers can validate payloads.
- [ ] Documented policy: breaking vs additive changes vs `schema_version`.

**Verification:**

- [ ] Example `jsonschema` or manual validation test against golden fixture.
- [ ] README links to schema + policy.

**Dependencies:** Tasks 4–5  

**Files likely touched:**

- `schemas/` or `docs/` (new)
- `secureli/modules/shared/scan_output/json_payload.py` (constants / docstrings only if needed)
- `README.md`

**Estimated scope:** Small–Medium

---

### Task 13: SARIF `ruleId` policy + GitHub Advanced Security uplift

**Description:** Choose and implement a stable **`ruleId`** strategy (raw **`ScanFailure.id`** vs prefixed by source e.g. **`hooks:`/`custom:`**); extend SARIF payload toward a **target consumer** (document which: e.g. GH Code Scanning ingestion, enterprise viewer). Iterate **locations**, fingerprints, or taxonomies only as required by that consumer—keep minimal path until the target is fixed.

**Acceptance criteria:**

- [ ] Written decision in README or ADR; SARIF builder matches it.
- [ ] Smoke validation against chosen consumer or documented manual upload steps.
- [ ] Tests updated for `ruleId`/result shape.

**Verification:**

- [ ] Golden / integration test for representative failure set.
- [ ] Optional CI snippet for SARIF upload (if GHAS is the target).

**Dependencies:** Task 6; aligns with spec open question on `ruleId`  

**Files likely touched:**

- `secureli/modules/shared/scan_output/sarif_payload.py`
- `tests/modules/shared/scan_output/test_sarif_payload.py`
- `README.md`
- `.github/workflows/*.yml` (optional SARIF upload job)

**Estimated scope:** Medium (larger if GHAS parity is deep)

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Pydantic v2 migration** blows up test fixtures | High | Migrate in batches; grep `.dict`/v1 validators; characterization tests before refactors |
| **`dependency-injector` + 3.12** still flaky | High | Pin exact working rev; document; watch upstream PR |
| **SARIF** consumers reject minimal output | Medium | Document limitations; iterate rule/locations after MVP |
| **`poe test` self-`init`** masks local `.secureli` drift | Medium | Periodic clean clone CI job optional; doc for contributors |

---

## Open questions

(Same as spec; resolve during implementation.)

- CI: single-version jobs vs explicit matrix (**3.9**, **3.11**, **3.12**)?
- SARIF **`ruleId`**: raw **`ScanFailure.id`** vs prefixed by source?
- **`pydantic-settings`**: dedicated contract tests for env/yaml loaders?

---

## Parallelization

| Parallel after foundation | Sequential |
|-------------------------|------------|
| Task 7 (**dry-run**) can run in parallel **only if** **`main.py` conflicts are manageable** — prefer sequencing **7 after 5** to reduce `init`/scan churn in Typer edits. | Tasks 4 → 5 → 6 (JSON before SARIF). |
| Task 9 (docs) drafts can start early as flags stabilize. | Task 8 after container patterns settled from Task 5. |

---

## Task index (quick checklist)

- [ ] **Task 1:** Python 3.12 + dependency-injector  
- [ ] **Task 2:** Pydantic v2 + pydantic-settings  
- [ ] **Task 3:** CI 3.12  
- [ ] **Checkpoint: Foundation**  
- [ ] **Task 4:** JSON scan_output module  
- [ ] **Task 5:** `--format json` wired  
- [ ] **Task 6:** SARIF + `--format sarif`  
- [ ] **Checkpoint: Scan formats**  
- [ ] **Task 7:** `init --dry-run`  
- [ ] **Task 8:** `doctor`  
- [ ] **Task 9:** README / CI snippet  
- [ ] **Checkpoint: MVP complete**  
- [ ] **Task 10:** Clean-clone CI + `poe e2e`  
- [ ] **Task 11:** `pydantic-settings` env/yaml contract tests  
- [ ] **Task 12:** JSON Schema + `schema_version` policy (`scan --format json`)  
- [ ] **Task 13:** SARIF `ruleId` + GHAS (or chosen consumer) uplift
