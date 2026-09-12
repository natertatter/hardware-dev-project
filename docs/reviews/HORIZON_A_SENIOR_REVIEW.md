# Horizon A — Senior Review & Remediation Handoff

Branch: `cursor/horizon-a-roadmap-be2c` (PR #15). Reviewed commits `06ac7ef`, `0fec84f`.
Automated status at review time: `pytest` 113 pass, `vitest` 20 pass, `tsc --noEmit` clean, `horizon_a_verify --write-firmware` pass.

The automated loop is green, which is exactly why these were missed: none of the defects below are covered by an existing test. This document is written to be handed to an implementation model. Each task has **Files**, **Why**, **Change**, and **Done when**.

---

## Check 1 — Backend persistence & safety (API, loaders, disk contract)

### 1.1 Path traversal in `project_id` (write paths are new) — **BLOCKER**

- **Files:** `src/eda_platform/api/project_loader.py`, `src/eda_platform/api/routes/projects.py`, `src/eda_platform/api/routes/operations.py`
- **Why:** `project_directory(project_id)` is `_PROJECTS_DIR / project_id` with no validation. Verified: `project_directory("../../tmp/evil")` resolves to `/workspace/projects/../../tmp/evil`. Before this branch only read paths and operations writes were exposed; A1 added `PUT /projects/{id}/schematic` and `PUT /projects/{id}/metadata`, so an arbitrary `project_id` now writes JSON outside `projects/`. `ProjectState.project_id` is only `min_length=1`.
- **Change:**
  1. Add `PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")` and `validate_project_id(project_id: str) -> str` in `project_loader.py` that raises `ValueError` on mismatch. Call it inside `project_directory()` so every loader/saver is covered.
  2. In `routes/projects.py` and `routes/operations.py`, catch `ValueError` from the loader and return **400** (`detail="invalid project_id"`). Prefer a shared FastAPI dependency `def project_id_param(project_id: str) -> str` used by all `/projects/{project_id}/...` routes.
  3. Mirror the rule in the UI: `ui/src/store/useSchematicStore.ts` `createProject` already uses `^[a-zA-Z][a-zA-Z0-9_-]*$`; move that regex to `ui/src/constants/project.ts` as `PROJECT_ID_PATTERN` so both sides share one definition.
- **Done when:** `tests/api/test_projects.py` has cases for `..`, `a/b`, `..%2Fx`, empty, and a 65-char id → all **400/422**; `pytest` passes; `project_directory("..")` raises.

### 1.2 Placeholder net is persisted to disk — **HIGH**

- **Files:** `src/eda_platform/api/routes/projects.py`, `src/eda_platform/api/routes/architect.py`, `ui/src/utils/decompileProjectState.ts`
- **Why:** `put_project_schematic` reuses `_draft_to_project_state`, which injects `_draft_placeholder` (a 1-connection SIGNAL net on the MCU GND pin) so `ProjectState` validates. Verified: a placement-only save writes `nets: [{"net_id": "_draft_placeholder", ...}]` into `schematic.json`. That synthetic net now flows into Logic Checker, `horizon_a_verify`, firmware codegen, and any downstream consumer of the file. Auto-wire strips it (`architect.py` lines 64–69); the save route does not.
- **Change (pick one; A is recommended):**
  - **A.** Persist a dedicated on-disk model. Add `SchematicFile(BaseModel)` in `api/schemas.py` = `project_id`, `nodes` (min 1), `nets` (may be empty). `save_project_state` accepts `ProjectState | SchematicDraft`; `load_project_state` returns `ProjectState | None` only when `nets` non-empty, plus a new `load_schematic_draft()` returning the raw file. `GET /schematic` returns the draft form. Callers needing a strict `ProjectState` (operations routes, firmware) keep using `load_project_state` and 422 when nets are empty ("wire the schematic before …").
  - **B.** Keep `ProjectState` on disk but make `PUT /schematic` refuse placement-only drafts with 422 (`"save requires at least one net — wire pins or run Auto-Wire first"`) and have the UI surface that message.
- Regardless of option: make `GET /projects/{id}/schematic` and `decompileProjectState` drop any net whose `net_id` starts with `_draft_` as defense in depth, and move the literal `"_draft_placeholder"` to one constant (`api/routes/architect.py` → `DRAFT_PLACEHOLDER_NET_ID`) imported by both routes.
- **Done when:** `test_placement_only_draft_save` asserts no `_draft_*` net in the file on disk (or asserts 422 for option B); UI vitest for `decompileProjectState` ignores `_draft_*` nets.

### 1.3 Schematic save does not invalidate operations approval — **MEDIUM**

- **Files:** `src/eda_platform/api/routes/projects.py`
- **Why:** `put_project_schematic` clears `schematic_approved` but leaves `operations_approved=True`. Operations steps bind to `node_id`s; a re-saved schematic can delete or rename nodes, leaving an approved-but-invalid operations master. The UI already resets both on canvas edits (`resetWorkflowState`), so the server contract is weaker than the client.
- **Change:** In `put_project_schematic`, set `metadata.operations_approved = False` alongside `schematic_approved = False`. Only when the incoming draft differs from what is on disk (compare `model_dump()` of nodes+nets) — a no-op save should not revoke approvals (see 2.2).
- **Done when:** test saves a schematic to a project whose metadata has both approvals true → both false; test saves identical content → approvals unchanged.

### 1.4 Tests write artifacts into the real repo tree — **HIGH (hygiene, root cause of two commit clean-ups)**

- **Files:** `tests/api/test_operations.py` (creates `projects/api_test_ops/`, `projects/demo_robot_merge_test/`), `tests/api/test_librarian.py` / `tests/agents/test_librarian_ingest.py` (writes `hardware_library/datasheets/bme280_datasheet.pdf`), new `tests/conftest.py`
- **Why:** These are pre-existing, but Horizon A made them visible: `horizon_a_verify.py` reported "2 project(s)" after a test run, and both branch commits had to be amended to strip accidental artifacts. CI will also mutate the checkout mid-run.
- **Change:**
  1. Add `tests/conftest.py` with an **autouse** fixture that monkeypatches `eda_platform.api.project_loader._PROJECTS_DIR` to `tmp_path_factory.mktemp("projects")` and copies `projects/demo_robot/` into it (tests that read `demo_robot` continue to work). Remove the now-redundant per-test fixture in `tests/api/test_projects.py`.
  2. Same pattern for `eda_platform.api.manifest_loader._MANIFESTS_DIR` is **not** needed (read-only), but librarian tests must redirect the datasheets dir: expose `_DATASHEETS_DIR` in `agents/librarian/ingest.py` (or the librarian route) and monkeypatch it.
  3. Add to `.gitignore` as a backstop: `projects/*/operations/drafts/`, `projects/*/operations/refined/`, `hardware_library/datasheets/*.pdf` with `!hardware_library/datasheets/.gitkeep`.
- **Done when:** `pytest -q && git status --porcelain` prints nothing.

### 1.5 `scripts/horizon_a_verify.py` couples to global `projects/` state — **LOW**

- **Files:** `scripts/horizon_a_verify.py`, `tests/test_horizon_a_verify.py`
- **Why:** The script asserts `demo_robot in project_ids` against the real directory and imports `TestClient` (pulls `httpx` into a "script"). Fine for CI, but the pytest wrapper makes the suite depend on repo-tree state and spawns a subprocess.
- **Change:** Keep the script for CI/humans. Change `tests/test_horizon_a_verify.py` to import and call `verify_pipeline(write_firmware=True, output_root=tmp_path)` directly (no subprocess) under the conftest tmp projects dir. Use `sys.exit` only in `main()`; have `verify_*` raise a `VerifyError` so they are testable.
- **Done when:** the test no longer shells out; it asserts `make` ran when toolchain present.

### 1.6 Docker image has no seed project — **LOW (docs/DX)**

- **Files:** `Dockerfile.api`, `docs/HOW_TO.md`
- **Why:** `Dockerfile.api` copies `src` and `hardware_library` only. Running the image without the Compose `projects/` bind mount yields an empty project list, and the UI's bootstrap then loads nothing.
- **Change:** `COPY projects/demo_robot ./projects/demo_robot` in `Dockerfile.api` (the bind mount overrides it under Compose). Add one sentence to HOW_TO under "Run it".
- **Done when:** `docker build -f Dockerfile.api .` then `docker run -p 8000:8000 <img>` → `GET /api/v1/projects` returns `["demo_robot"]`.

---

## Check 2 — UI workflow state, tests, CI

### 2.1 Operations approval is never persisted from the UI — **HIGH (A1 contract gap)**

- **Files:** `ui/src/store/useOperationsStore.ts`, `ui/src/lib/api.ts`, `ui/src/store/useSchematicStore.ts` (`loadProject`)
- **Why:** `approveOperations` only sets `operationsApproved: true` in memory. `POST /api/v1/projects/{id}/operations/approve` exists and writes `metadata.operations_approved`, but nothing calls it. On reload, `loadProject` hydrates `operationsApproved` from metadata → the flag silently reverts to `false`. Schematic approval *is* persisted (`approveSchematic`), so the two gates behave differently.
- **Change:**
  1. Add `approveOperationsOnServer(projectId)` to `lib/api.ts` → `POST /projects/{id}/operations/approve`.
  2. `approveOperations` becomes async: requires `operationsStatus === "pass"`, ensures the active sequence is merged to master (call `mergeToMaster` if `refinedSequence !== sequence` or master missing), then calls the approve endpoint, then sets the flag. Surface server 404/422 as `operationsMessage` (e.g. "Save the schematic before approving operations").
  3. The endpoint requires `schematic.json` on disk; make `approveSchematic` save the schematic first (see 2.2) so this ordering holds naturally.
- **Done when:** vitest: approving operations calls the endpoint and, on 422, leaves `operationsApproved=false` with a message; manual: approve → reload → still approved.

### 2.2 Approve/Save ordering revokes approval; approve is fire-and-forget — **HIGH (UX correctness)**

- **Files:** `ui/src/store/useSchematicStore.ts` (`approveSchematic`, `saveProject`)
- **Why:** Current flow: Validate → Approve (persists `schematic_approved=true` for whatever is on disk, which may be stale) → Save (server + client clear `schematic_approved`). The user must re-validate and re-approve after every save, and the approved flag on disk can refer to a schematic that was never saved. Additionally `approveSchematic` swallows all errors in a detached `void (async …)`, so an offline API shows "Approved" with nothing persisted; and `saveProject` performs two redundant metadata round-trips after the server already reset the flag.
- **Change:**
  1. `approveSchematic` becomes `async`: `buildSchematicDraft` → `saveProjectSchematic` → `fetchProjectMetadata` → `saveProjectMetadata({schematic_approved: true})` → then `set({schematicApproved: true})`. On error set `projectStatus: "error"` and a message; do **not** set approved.
  2. `saveProject`: drop the post-save `fetchProjectMetadata`/`saveProjectMetadata` block (server owns that). Only clear `schematicApproved` if the draft differs from the last saved draft; keep `lastSavedDraftHash: string | null` in the store (`JSON.stringify` of nodes/nets is adequate).
  3. Replace `let metadata` with `const` in `loadProject` (prefer-const).
- **Done when:** vitest: approve calls save then metadata in order and fails closed on rejected fetch; saving unchanged content keeps approval.

### 2.3 `loadProject` failure leaves inconsistent state — **MEDIUM**

- **Files:** `ui/src/store/useSchematicStore.ts` (`loadProject`)
- **Why:** `projectId` is set to the target **before** the fetch. On failure the `<select>` shows the new id while `nodes/edges`, approvals, and the operations store still belong to the previous project; subsequent Save would write the old canvas under the new id.
- **Change:** Capture `previousProjectId`; only commit `projectId` inside the success `set`. On failure restore `projectId: previousProjectId` and keep `projectStatus: "error"`.
- **Done when:** vitest: rejected `fetchProjectSchematic` leaves `projectId` unchanged.

### 2.4 Loaded master is treated as a "refined" sequence and gates firmware — **MEDIUM**

- **Files:** `ui/src/store/useOperationsStore.ts` (`hydrateFromDisk`), `ui/src/components/SchematicEditor.tsx`
- **Why:** `hydrateFromDisk` sets `refinedSequence = master`. `SchematicEditor` disables **Generate Firmware** when `refinedSequence != null && !operationsApproved`. After loading `demo_robot` (a `narrative` master with zero steps) the button is locked until the user runs Validate → Approve operations, even though nothing behavioural exists. Also the sidebar labels a persisted master as refined output.
- **Change:** Hydrate `sequence = master` and `refinedSequence = null`. Introduce a selector `hasActiveOperations = getActiveSequence()?.steps.length > 0 || fidelity !== "narrative"` and use it for the firmware gate instead of `refinedSequence != null`. Keep the existing rule that when an active sequence exists it must be approved.
- **Done when:** vitest: hydrating a narrative, zero-step master does not block firmware; hydrating a `timed` master does until approved.

### 2.5 `createProject` can silently overwrite an existing project — **MEDIUM**

- **Files:** `ui/src/store/useSchematicStore.ts` (`createProject`)
- **Why:** No collision check against `projectIds`; the next Save overwrites `projects/<id>/schematic.json` and resets its approvals.
- **Change:** If `projectIds.includes(projectId)` set `projectStatus: "error"` + message "Project already exists — select it from the list." Also share the regex from 1.1.
- **Done when:** vitest covers collision.

### 2.6 UI test gaps for everything A1 added — **HIGH**

- **Files:** `ui/src/store/useSchematicStore.test.ts`, new `ui/src/utils/buildSchematicDraft.test.ts`, `ui/src/store/useOperationsStore.test.ts`
- **Why:** Zero tests exercise `loadProject`, `saveProject`, `createProject`, `refreshProjectList`, `hydrateFromDisk`, or `buildSchematicDraft`. The `beforeEach` in `useSchematicStore.test.ts` does not reset `projectId/projectIds/projectStatus/projectMessage`, so state can leak between tests once they exist.
- **Change:** Mock `@/lib/api` (pattern already used in `useOperationsStore.test.ts`). Add: load success (nodes/edges/approvals hydrated, ops store hydrated), load failure (2.3), save placement-only sends `nets: []`, save wired sends compiled nets, create collision (2.5), approve ordering (2.2), `buildSchematicDraft` for 0 nodes / 0 edges / wired.
- **Done when:** ≥ 8 new vitest cases; all pass.

### 2.7 CI hardening — **MEDIUM**

- **Files:** `.github/workflows/ci.yml`, `ui/package.json`
- **Why:** UI job uses `npm install` (lockfile drift) and never type-checks; `next lint` is declared but ESLint is not a devDependency, so `npm run lint` fails locally. The Python job runs `horizon_a_verify --write-firmware` without `gcc`/`make` guaranteed — the script skips compile silently, so CI never proves the generated C builds (the `test_firmware_compiles.py` suite also skips).
- **Change:**
  1. `npm install` → `npm ci`; add `npx tsc --noEmit` step; add `eslint` + `eslint-config-next` devDependencies and a `lint` CI step (or delete the `lint` script).
  2. Python job: `sudo apt-get install -y build-essential` before pytest so compile tests and the verify script's `make` actually run; assert in the verify script that compile ran when `--require-toolchain` is passed and pass that flag in CI.
  3. Add `concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }`.
- **Done when:** CI logs show `OK — make succeeded` and a tsc step.

### 2.8 Hidden default `project_id` in `compileProjectState` — **LOW**

- **Files:** `ui/src/utils/compileProjectState.ts`
- **Why:** Default changed from `"schematic_project"` to `"demo_robot"`. A missed call site now silently tags data as the demo project — the exact class of bug A1 set out to remove.
- **Change:** Make `projectId` a required parameter; fix the compiler errors (all call sites already pass it except tests — update `compileProjectState.test.ts`).
- **Done when:** `tsc --noEmit` passes with no default.

### 2.9 Docs drift — **LOW**

- **Files:** `docs/HOW_TO.md`, `docs/architecture/API.md`, `docs/ROADMAP.md`
- **Why:** HOW_TO operations table still says Merge "uses in-memory schematic"; API.md must document the 400 on invalid `project_id` (1.1), the draft/empty-nets behaviour chosen in 1.2, and the operations-approval reset in 1.3. ROADMAP marks A1 "Done" but operations approval persistence (2.1) is part of the A1 "metadata.json" criterion — downgrade to "Done (pending review fixes)" until this list closes.
- **Done when:** the three docs reflect the final behaviour; ROADMAP "Last reviewed" bumped.

---

## Execution plan for the implementation model

Work **on this branch**, one commit per numbered item (commit subject `Review 1.x: …` / `Review 2.x: …`). Run the loop after every commit:

```bash
python3 -m pytest -q && git status --porcelain          # must be empty after 1.4
cd ui && npx tsc --noEmit && npx vitest run && cd ..
python3 scripts/horizon_a_verify.py --write-firmware
```

**Order (dependencies first):**

1. **1.4** conftest + gitignore — stops the suite from dirtying the tree; everything after is cleaner to verify.
2. **1.1** project-id validation (backend) + shared regex constant (UI).
3. **1.2** placeholder-net persistence (choose option A unless told otherwise). Update `test_projects.py`.
4. **1.3** operations approval reset on schematic change (+ no-op save preserves approvals).
5. **2.2** approve-saves-first / save-preserves-approval / `const metadata`.
6. **2.1** operations approval persisted via `/operations/approve`.
7. **2.4** hydrate as `sequence`, firmware gate via `hasActiveOperations`.
8. **2.3**, **2.5** load-failure rollback, create collision.
9. **2.8** required `projectId` param.
10. **2.6** UI tests for all of the above (write them alongside 5–9 where practical).
11. **1.5**, **1.6** verify-script test refactor, Docker seed.
12. **2.7** CI hardening.
13. **2.9** docs; bump ROADMAP.

**Constraints:**
- Do not change `ProjectState` schema semantics (`nets` min 1) — the Logic Checker and firmware engine depend on it; isolate "draft" leniency to the persistence layer (1.2 option A).
- Keep `DEFAULT_PROJECT_ID = "demo_robot"` as the UI bootstrap default.
- No new runtime dependencies on the Python side; UI may add `eslint` dev dependencies only.
- Preserve existing test names in `tests/api/test_operations.py`; only redirect their disk writes.

**Definition of done for the branch:** all items above closed, loop green, `git status` clean after tests, CI shows tsc + lint + compiled firmware, PR #15 description updated with a "Review fixes" section listing 1.1–2.9.
