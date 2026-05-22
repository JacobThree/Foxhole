---
name: spec-driven-development
description: Creates specs before coding. Use when starting a new project, feature, or significant change and no specification exists yet. Use when requirements are unclear, ambiguous, or only exist as a vague idea.
---

# Spec-Driven Development

## Overview

Write a structured specification before writing any code. The spec is the shared source of truth between you and the human engineer — it defines what we're building, why, and how we'll know it's done. Code without a spec is guessing.

## When to Use

- Starting a new project or feature
- Requirements are ambiguous or incomplete
- The change touches multiple files or modules
- You're about to make an architectural decision
- The task would take more than 30 minutes to implement

**When NOT to use:** Single-line fixes, typo corrections, or changes where requirements are unambiguous and self-contained.

## The Gated Workflow

Spec-driven development has four phases. Do not advance to the next phase until the current one is validated.

```
SPECIFY ──→ PLAN ──→ TASKS ──→ IMPLEMENT
   │          │        │          │
   ▼          ▼        ▼          ▼
 Human      Human    Human      Human
 reviews    reviews  reviews    reviews
```

### Phase 1: Specify

Start with a high-level vision. Ask the human clarifying questions until requirements are concrete.

**Surface assumptions immediately.** Before writing any spec content, list what you're assuming:

```
ASSUMPTIONS I'M MAKING:
1. This is a web application (not native mobile)
2. Authentication uses session-based cookies (not JWT)
3. The database is PostgreSQL (based on existing Prisma schema)
4. We're targeting modern browsers only (no IE11)
→ Correct me now or I'll proceed with these.
```

Don't silently fill in ambiguous requirements. The spec's entire purpose is to surface misunderstandings *before* code gets written — assumptions are the most dangerous form of misunderstanding.

**Write a spec document covering these six core areas:**

1. **Objective** — What are we building and why? Who is the user? What does success look like?

2. **Commands** — Full executable commands with flags, not just tool names.
   ```
   Build: npm run build
   Test: npm test -- --coverage
   Lint: npm run lint --fix
   Dev: npm run dev
   ```

3. **Project Structure** — Where source code lives, where tests go, where docs belong.
   ```
   src/           → Application source code
   src/components → React components
   src/lib        → Shared utilities
   tests/         → Unit and integration tests
   e2e/           → End-to-end tests
   docs/          → Documentation
   ```

4. **Code Style** — One real code snippet showing your style beats three paragraphs describing it. Include naming conventions, formatting rules, and examples of good output.

5. **Testing Strategy** — What framework, where tests live, coverage expectations, which test levels for which concerns.

6. **Boundaries** — Three-tier system:
   - **Always do:** Run tests before commits, follow naming conventions, validate inputs
   - **Ask first:** Database schema changes, adding dependencies, changing CI config
   - **Never do:** Commit secrets, edit vendor directories, remove failing tests without approval

**Spec template:**

```markdown
# Spec: [Project/Feature Name]

## Objective
[What we're building and why. User stories or acceptance criteria.]

## Tech Stack
[Framework, language, key dependencies with versions]

## Commands
[Build, test, lint, dev — full commands]

## Project Structure
[Directory layout with descriptions]

## Code Style
[Example snippet + key conventions]

## Testing Strategy
[Framework, test locations, coverage requirements, test levels]

## Boundaries
- Always: [...]
- Ask first: [...]
- Never: [...]

## Success Criteria
[How we'll know this is done — specific, testable conditions]

## Open Questions
[Anything unresolved that needs human input]
```

**Reframe instructions as success criteria.** When receiving vague requirements, translate them into concrete conditions:

```
REQUIREMENT: "Make the dashboard faster"

REFRAMED SUCCESS CRITERIA:
- Dashboard LCP < 2.5s on 4G connection
- Initial data load completes in < 500ms
- No layout shift during load (CLS < 0.1)
→ Are these the right targets?
```

This lets you loop, retry, and problem-solve toward a clear goal rather than guessing what "faster" means.

### Phase 2: Plan

With the validated spec, generate a technical implementation plan:

1. Identify the major components and their dependencies
2. Determine the implementation order (what must be built first)
3. Note risks and mitigation strategies
4. Identify what can be built in parallel vs. what must be sequential
5. Define verification checkpoints between phases

The plan should be reviewable: the human should be able to read it and say "yes, that's the right approach" or "no, change X."

### Phase 3: Tasks

Break the plan into discrete, implementable tasks:

- Each task should be completable in a single focused session
- Each task has explicit acceptance criteria
- Each task includes a verification step (test, build, manual check)
- Tasks are ordered by dependency, not by perceived importance
- No task should require changing more than ~5 files

**Task template:**
```markdown
- [ ] Task: [Description]
  - Acceptance: [What must be true when done]
  - Verify: [How to confirm — test command, build, manual check]
  - Files: [Which files will be touched]
```

### Phase 4: Implement

Execute tasks one at a time following `incremental-implementation` and `test-driven-development` skills. Use `context-engineering` to load the right spec sections and source files at each step rather than flooding the agent with the entire spec.

## Keeping the Spec Alive

The spec is a living document, not a one-time artifact:

- **Update when decisions change** — If you discover the data model needs to change, update the spec first, then implement.
- **Update when scope changes** — Features added or cut should be reflected in the spec.
- **Commit the spec** — The spec belongs in version control alongside the code.
- **Reference the spec in PRs** — Link back to the spec section that each PR implements.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "This is simple, I don't need a spec" | Simple tasks don't need *long* specs, but they still need acceptance criteria. A two-line spec is fine. |
| "I'll write the spec after I code it" | That's documentation, not specification. The spec's value is in forcing clarity *before* code. |
| "The spec will slow us down" | A 15-minute spec prevents hours of rework. Waterfall in 15 minutes beats debugging in 15 hours. |
| "Requirements will change anyway" | That's why the spec is a living document. An outdated spec is still better than no spec. |
| "The user knows what they want" | Even clear requests have implicit assumptions. The spec surfaces those assumptions. |

## Red Flags

- Starting to write code without any written requirements
- Asking "should I just start building?" before clarifying what "done" means
- Implementing features not mentioned in any spec or task list
- Making architectural decisions without documenting them
- Skipping the spec because "it's obvious what to build"

## Verification

Before proceeding to implementation, confirm:

- [ ] The spec covers all six core areas
- [ ] The human has reviewed and approved the spec
- [ ] Success criteria are specific and testable
- [ ] Boundaries (Always/Ask First/Never) are defined
- [ ] The spec is saved to a file in the repository

---

# Spec: seCureLI modernization MVP (2026)

This section is the **active product spec** for this fork. Process guidance above still applies; implement work against this document and keep it updated when scope changes.

## Objective

Bring the CLI to a **maintainable, 2026-ready baseline** without a rewrite: current Python support, machine-readable scan output for automation and GitHub, safer `init` UX, and a quick health check command. Success = upstream parity on core flows plus these four deliverables, clean CI, and no new default telemetry or secret exfiltration.

**Users:** developers running seCureLI locally and in CI; maintainers extending the Python codebase.

**Non-goals (this spec):** Rust core, AI remediation, SBOM/license suites, opinionated profiles (startup/enterprise), HTML report UI, plugin registry, full policy-as-code.

## Repository baseline (fact check against this fork)

Ground truth so implementation does not contradict the codebase:

| Area | Current state |
|------|----------------|
| **Python range** | `pyproject.toml` pins `python = ">= 3.9, < 3.12"` with comments that **`dependency-injector`** blocks 3.12 until a release (upstream PR/link noted in-repo: ets-labs/python-dependency-injector#765); optional git branch pin is documented in comments. |
| **Pydantic** | **v1** today (`pydantic ^1.10.2`): models in `secureli/modules/shared/models/scan.py` use `pydantic.BaseModel`; `secureli/settings.py` uses **`pydantic.BaseSettings`** (v1 pattern). Migrating to v2 implies **`pydantic-settings`** for settings and touching all BaseModel/BaseSettings usages. |
| **CLI** | Typer `app` in `secureli/main.py`; console script `secureli = secureli.main:app` in `pyproject.toml`. |
| **Scan pipeline** | `ScanAction.scan_repo` merges **custom scanners** (`PiiScannerService`, `CustomRegexScannerService`) and **hooks** (`HooksScannerService` → `PreCommitAbstraction.execute_hooks`). Both contribute to merged `ScanResult` / failures. Machine output must cover **both** paths, not only pre-commit stderr. |
| **Failure shape** | `ScanFailure` fields today: **`repo`, `id`, `file`, `exitCode`** (camelCase attribute names). JSON/SARIF mappers should use this model (aliases if external API wants snake_case). |
| **Exit behavior** | On failed scan, `ScanAction` calls `sys.exit(ExitCode.SCAN_ISSUES_DETECTED)` — **`--format` must preserve non-zero exit** when findings exist. |
| **Remote logs** | `secureli scan` defaults `publish_results` to **`never`** (`main.py`). Spec boundary “no new default telemetry” matches current CLI defaults; optional observability POST remains explicit opt-in. |
| **Pre-commit config path** | Canonical path under **`.secureli/.pre-commit-config.yaml`** (`PreCommitAbstraction` deprecates repo-root config; migration prompts exist in `secureli/actions/action.py`). Poe task runs `pre-commit` with **`--config .secureli/.pre-commit-config.yaml`**. **`init` / `--dry-run` must respect the same paths and migration behavior.** |
| **CI Python versions** | **`.github/workflows/build_and_test.yml`**: Linux + Windows jobs both use **`python-version: "3.9"`** only (no version matrix yet). **`smoke_testing.yml`**: Windows smoke **`3.10`**, PyPI macOS smoke **`3.11`** (comment ties 3.11 to dependency-injector / 3.12). **`publish.yml`**: **`3.9`**. MVP work item: run **automated tests** on **3.12** once supported (matrix or extra job), not only smoke workflows. |

## Assumptions (still require human confirmation if violated)

1. CLI stays **Python + Typer**; **`dependency-injector` container** stays for composing actions/services (refactors keep `secureli/container.py` wiring viable).
2. **Pre-commit** remains execution engine for **hook-based** scans; custom scanners remain **native Python** in-process (no rewrite to external processes for MVP).
3. **SARIF 2.1.0** at minimal completeness (runs, rules/results with stable `ruleId` / message / location where data exists); GitHub Advanced Security parity is follow-up.
4. **Public JSON schema** from `secureli scan --format json` can ship as **MVP-stable** (`version` field recommended); semver discipline later.
5. **Python 3.12 adoption** resolves via updated **`dependency-injector`** pin (PyPI release and/or pinned git revision) per team comfort — tracked outcome: `pyproject.toml` allows **3.12** and CI proves it.

## Tech stack

- **Goal:** Add **Python 3.12** to the supported range while keeping **3.9–3.11** working **unless** an intentional breaking release documents dropped versions in CHANGELOG.
- **Baseline today:** Poetry, Typer **>=0.6,<0.13**, Pre-commit library **>=2.20,<4.0**, Pydantic **v1 → migrate to v2** + **`pydantic-settings`**, pytest/poe tasks as today.

## Commands (target surface)

```bash
# Existing — keep working
poetry install
poetry run poe test        # runs init, lint, coverage (see pyproject tool.poe.tasks)
poetry run secureli scan
poetry run secureli init

# New / extended
poetry run secureli scan --format text    # default; current behavior (Rich/plain terminal output)
poetry run secureli scan --format json
poetry run secureli scan --format sarif
poetry run secureli init --dry-run        # no writes; print planned changes
poetry run secureli doctor                # environment + repo readiness checks
```

**CI:** There is **no** multi-version matrix in `build_and_test.yml` today; add jobs or a matrix so **3.12** is exercised beside **3.9** (and align `smoke_testing.yml` comments once 3.12 ships).

## Project structure (touch points)

- `secureli/main.py` — Typer commands / **`--format` on `scan`**, **`--dry-run` on `init`**, register **`doctor`**.
- `secureli/actions/scan.py` — Branch output by format after merged `scan_result`; keep **`sys.exit(ExitCode.SCAN_ISSUES_DETECTED)`** path on failures.
- `secureli/container.py` — Wire new formatter service or pure functions into `ScanAction` if using DI (match existing factories).
- New module e.g. `secureli/modules/shared/scan_output/` — JSON + SARIF builders (**input:** `ScanResult`, **`list[ScanFailure]`**, optional raw `output` string); pure, unit-tested.
- `secureli/actions/initializer.py` — **`--dry-run`**: reuse planning logic, **skip writes** under `.secureli/` (and legacy root pre-commit migration if that path still applies).
- New `secureli/actions/doctor.py` (and/or small services) — read-only checks (**Python version**, **`pre-commit` CLI**, readable `.secureli` / config presence).
- `tests/application/test_main.py` — extend CLI tests; add unit tests beside `tests/` mirrors for new helpers.

## Code style

- Match existing module layout, type hints, and Typer `Option` patterns.
- Formatters take a structured in-memory result (reuse or extend `ScanResult` / failures list), not raw ANSI strings.
- SARIF: build a dict matching SARIF 2.1.0 schema where practical; validate with a focused test (golden file or required keys).

Example (illustrative — align with **`ScanFailure`**: `repo`, `id`, `file`, `exitCode`):

```python
def scan_failures_to_sarif(failures: list[ScanFailure], tool_driver: str) -> dict:
    """Return SARIF Log dict; no I/O."""
    ...
```

## Testing strategy

### Commands (today)

Per `pyproject.toml` **`tool.poe.tasks`**:

| Task | What runs | Relevance to MVP |
|------|-----------|------------------|
| **`poe test`** | **`init`** (`secureli init -y` on workspace) → **`lint`** (`black --check`) → **`coverage_run`** (`coverage run -m pytest`) → **`coverage_report`** | Anything that regenerates **`./.secureli/`** during `secureli_init` affects every PR; refactoring must keep **workspace self-init + pytest** green. Prefer not to widen `secureli_init` scope without deliberate choice. |
| **`poe e2e`** | BATS on `tests/end-to-end/` | Shell-level regressions (`init`, `scan`, preserves hooks, language detection). Extend only when MVP behavior truly needs subprocess/real-fs proof beyond pytest. |
| **`poe lang-test`** | Subset BATS (`test-language-detect.bats`) | Quick language-detection churn check. |

**Plugins / runners:** **`pytest`** with **`pytest-mock`**; Typer **`CliRunner`** in `tests/application/test_main.py`. Global fixtures in **`tests/conftest.py`** (`mock_pre_commit`, `mock_secureli_config`, …); **`tests/actions/conftest.py`** for action-layer echo/logging/language mocks.

### Test layout (inventory)

| Layer | Paths | Typical focus |
|-------|--------|----------------|
| **Actions** | `tests/actions/` — **`test_scan_action.py`** (large fixture set), **`test_initializer_action.py`**, `test_update_action.py`, `test_action.py`, `test_build_action.py` | **`ScanAction`**: merged hook + custom scanner results, logging, **`sys.exit(ExitCode.SCAN_ISSUES_DETECTED)`** on failures. **`InitializerAction`**: verify paths, outcomes, logging. Best place for **dry-run**: assert **no writes** (`mock_secureli_config` / `mock_open` / patch `Path.write_*`). |
| **Application / CLI** | `tests/application/test_main.py`, `test_container.py`, `test_settings.py` | **Typer invocation**: mocks **`secureli.main.container`**, asserts `scan_repo(...)` kwargs. Adding **`--format`**, **`--dry-run`**, **`doctor`** → extend **`CliRunner`** tests **and** keep mock `scan_repo` / `initialize_repo` kwargs in sync when signatures change. |
| **Modules** | `tests/modules/**` — e.g. `test_hook_scanner_service.py`, `test_custom_scans.py`, `test_pre_commit.py`, scanners, language, utilities | Parsing hook output (`HooksScannerService`), **`ScanFailure`** population, abstraction behavior. Formatter unit tests (**new**) should live beside **`secureli.modules.shared`** (mirror `tests/modules/shared/...`). |
| **Repositories** | `tests/repositories/` | Config persist/load; tighten if **`init --dry-run`** distinguishes “would write” paths. |
| **E2E** | `tests/end-to-end/*.bats` + `test-data/` | Real CLI in temp dirs; optional for **`--format json`** if pytest gives enough confidence — add one BATS case only if regressions slipped through mocks. |

### How MVP milestones map to tests

| Milestone | Add / extend tests in | Notes |
|-----------|----------------------|-------|
| **Python 3.12 + Pydantic v2** | Entire `tests/` tree | **`BaseModel`/`BaseSettings`**, validators, **`model_dump`** vs `.dict()`, optional **`SecretStr`** behavior. **`ScanFailure`**, **`ScanResult`**, `Settings` imports break widely — migrate fixtures in batches; run **`poe coverage`** locally. **`test_container.py`** may need wiring updates if **`Container.providers` change.** |
| **JSON / SARIF formatters** | **`tests/modules/shared/scan_output/`** (or equivalent) — new files | Pure functions: **empty failures**, single **`ScanFailure`**, multiple repos/hooks; **JSON** `loads` smoke; SARIF `$schema`/required keys or golden **`json.dumps(..., sort_keys=True)`**. No subprocess. |
| **`scan --format`** | **`test_scan_action.py`** + **`test_main.py`** | Action: mocked `Echo` / print path — assert **exactly one** primary stream (stderr vs stdout) documented in code. CLI: **`CliRunner`** with format flags; **`scan_repo`** may gain optional **`output_format`** param — update **every** test that asserts `scan_repo(..., files=...)`. **`test_that_scan_implement*_file*`** patterns are the templates. Exit code: replicate existing **`pytest.raises(SystemExit)`** pattern for **`ExitCode.SCAN_ISSUES_DETECTED`** when failures + non-text format. |
| **`init --dry-run`** | **`test_initializer_action.py`** primarily; **`test_main.py`** for flag plumbing | **`initialize_repo`** likely gains **`dry_run: bool`** — thread from Typer; assert **`MagicMock`** write methods never called on config paths vs normal init. |
| **`doctor`** | **`tests/actions/test_doctor_action.py`** (new) + **`test_main.py`** | Mirrors other actions: thin Typer wrapper + mocked action; branch tests for missing **`pre-commit`**, bad Python?, missing `.secureli`. |

### Refactor hygiene (avoid spec drift)

- **Signature ripple:** `ScanAction.scan_repo` and Typer **`scan()`** signatures are echoed in **`test_main.py`** mocks — grep for **`scan_repo.assert_called`** when changing kwargs.
- **Don’t downgrade coverage** for new branches without reviewer sign-off; **`poe test`** already enforces repo-level **black**.
- Prefer **characterization tests** around formatter output shapes before refactoring parsers.
- **`pydantic v2`:** add a short **parity checklist** PR note (serialization of **`ScanFailure`**, **`LogAction`** payloads, **`Settings` env + yaml** loaders).

### Definition of ready (tests)

Before closing each MVP milestone: **`poetry run poe coverage`** (or **`poe test`** if CI-equivalent locally) passes; **new behavior has at least one test** at the lowest layer that catches the bug **and**—for user-facing flags—**one **`CliRunner`** test** proving the CLI passes options through unless exempted below.

**Golden / snapshots:** retain **one** stable **JSON** and **SARIF** exemplar blob (minimal failures) checked into **`tests/fixtures/`** or alongside the formatter tests.

## Boundaries

- **Always:** default `scan` output remains human **text** unless `--format` is set; never print raw secrets in JSON/SARIF (messages as delivered by hooks today — do not add new secret-bearing fields).
- **Ask first:** dropping Python 3.9/3.10 support, new runtime dependencies, changing default hook sets, semantic changes to `init` without `--dry-run`.
- **Never:** enable remote logging/telemetry by default; commit real credentials; vendor unrelated submodules for MVP.

## Success criteria

1. **Python 3.12** installs and passes test suite in CI; `python` constraint in `pyproject.toml` documents supported range.
2. `secureli scan --format json` writes **valid JSON** to stdout (or configured stream) and exits non-zero on failures; empty/failure cases covered by tests.
3. `secureli scan --format sarif` emits **SARIF 2.1.0** JSON with at least one `run` and `results` when failures exist; documented limitation if any field is omitted.
4. `secureli init --dry-run` performs **no filesystem writes** to **`.secureli/`** (including generated `.pre-commit-config.yaml`, `.secureli.yaml` updates, **`repo-config.yaml`**, logs) nor **destructive migration** from deprecated root `.pre-commit-config.yaml` unless/until product decision says otherwise — output lists planned actions; tested.
5. `secureli doctor` exits **0** when checks pass, **non-zero** with actionable messages when pre-commit missing, wrong Python, or expected config missing; documented in README.
6. README (short section) documents new flags and CI example snippet for `scan --format json` (SARIF optional line).

## Implementation order

1. Python 3.12 + Pydantic v2 + dependency fixes (unblocks everything else).
2. JSON formatter + `--format` wiring (simplest machine output).
3. SARIF formatter + tests.
4. `init --dry-run`.
5. `doctor` + docs.

## Open questions

- After 3.12 passes CI, retain **single-version** CI jobs vs explicit **matrix** (`3.9`, `3.11`, `3.12`) for cost vs coverage?
- **SARIF `ruleId`:** derive from **`ScanFailure.id`** uniformly (covers hooks + custom scans) or encode source channel (`hooks:` / `custom:`)?
- **`pydantic-settings`**: env prefix / `.env` behavior parity with today’s `Settings` loaders — any contract tests required?
