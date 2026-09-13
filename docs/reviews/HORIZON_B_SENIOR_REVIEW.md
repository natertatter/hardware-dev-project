# Horizon B — Senior Review & Remediation Handoff

Branch: `cursor/horizon-b-be2c` (PR #16). Reviewed commit `f7f8504` against `main` @ `2ff7ad2`.
Automated status at review time: `pytest` 122 pass / 1 skip, `vitest` 33 pass, `tsc --noEmit` clean, `horizon_a_verify --write-firmware --require-toolchain` pass.

Every check below is green, and every defect below is real. That is the same pattern as the Horizon A review: the suite passes because nothing exercises the new behavior end-to-end. The difference this time is worse, because Horizon B's entire premise is *"operations drive runtime firmware."* Several defects mean the generated firmware **does not match the operations sequence** while reporting success — including one case where a boot step is executed twice, one where declared periods are ignored entirely, and one where a `%` character in a step description emits firmware that reads uninitialized stack memory as a pointer.

This document is written to be handed to an implementation model. Each task has **Files**, **Why**, **Change**, **Done when**.

**Do not mark Horizon B done, and do not take PR #16 out of draft, until 1.1, 1.2, 1.3, 1.5, 1.9, 2.1, 2.3, 3.1, and 3.4 are fixed.** Start with **1.9** — it is the only item here that produces firmware which crashes on hardware.

---

## How to reproduce the empirical findings

The findings in Check 1 were produced with this probe. Keep it out of the repo, or land it as a test (see 3.4/3.5).

```python
# PYTHONPATH=/workspace python3 probe.py
from eda_platform.agents.firmware_engineer import generate_firmware
from eda_platform.agents.firmware_engineer.operations_runtime import build_runtime_plan
from eda_platform.schemas import FidelityLevel, OperationStep, OperationsSequence, TimingConstraint
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state

ops = OperationsSequence(
    project_id="valid_i2c_wiring", fidelity=FidelityLevel.TIMED,
    steps=[
        OperationStep(step_id="boot1", description="Enable power rail before sensors",
                      hal_call="hal_power_enable()", timing=TimingConstraint(delay_ms=100)),
        OperationStep(step_id="run1", description="Pause before reversing motor direction",
                      timing=TimingConstraint(delay_ms=500)),
        OperationStep(step_id="run2", description="Log bus current every second",
                      hal_call="hal_sensor_read()", timing=TimingConstraint(period_ms=1000)),
    ],
)
plan = build_runtime_plan(ops)
print([(s.step_id, s.delay_ms) for s in plan.startup_delays])
print([(s.step_id, s.period_ms, s.hal_call) for s in plan.periodic_steps])
```

Observed output:

```
startup_delays: [('run1', 500)]
periodic_steps: [('boot1', 20, 'hal_power_enable()'), ('run2', 1000, 'hal_sensor_read()')]
```

`boot1` is a boot step. It is already emitted as a `usleep` in `main()`. It should not be in `periodic_steps` at all.

---

## Check 1 — B1 runtime interpreter: does firmware actually match the sequence?

### 1.1 Boot steps with a `hal_call` are classified as boot **and** periodic — **BLOCKER**

- **Files:** `src/eda_platform/agents/firmware_engineer/operations_runtime.py` (`build_runtime_plan`)
- **Why:** The loop only `continue`s when a step has `delay_ms` **and** is *not* a boot step. A boot step with `delay_ms` therefore falls through to the periodic branch, where the condition `if period_ms or step.hal_call:` admits it because `hal_call` is set. Verified above: `boot1` ("Enable power rail before sensors", `delay_ms=100`, `hal_call` set) is emitted as `usleep(100000)` in `main.c` *and* as a line in `ops_runtime_on_poll_tick()` that then runs on every sensor poll tick forever. For a real power-rail or motor-enable HAL call (once 1.3 is fixed and these become real calls rather than `printf`), that is re-triggering an init operation at the poll rate on live hardware.
- **Change:** Make the partition explicit and total, with boot classification decided once:

```python
for step in operations.steps:
    timing = step.timing
    delay_ms = timing.delay_ms if timing else None
    period_ms = timing.period_ms if timing else None

    if delay_ms and is_boot_step(step.description):
        continue  # main() owns boot delays — see boot_delay_steps()
    if period_ms:
        periodic.append(...)
        continue
    if delay_ms:
        deferred.append(...)   # see 1.4 for naming
        continue
    if step.hal_call:
        periodic.append(...)   # unperiodized HAL step
```

  Each step must land in exactly one bucket. Add an assertion-style test that the union of `boot_delay_steps()` step ids and both plan buckets is a partition of `operations.steps` (no id in two buckets, no id dropped).
- **Done when:** a test with the probe's three-step sequence asserts `boot1` appears **only** in `boot_delay_steps()`; a parametrized test asserts partition-ness over a matrix of `(delay_ms, period_ms, hal_call, boot-wording)` combinations.

### 1.2 `period_ms` is recorded and then ignored — every periodic step fires at the sensor-poll rate — **BLOCKER**

- **Files:** `src/eda_platform/agents/firmware_engineer/codegen/templates.py` (`ops_interpreter_c`, `task_sensor_poll_c`), `operations_runtime.py`
- **Why:** `RuntimePeriodicStep.period_ms` is populated (from `timing.period_ms`, else a hardcoded `20`) and never used by any template. `ops_runtime_on_poll_tick()` unconditionally prints every periodic step, and it is called once per iteration of the sensor-poll loop, whose period is `SENSOR_POLL_PERIOD_MS` from the scheduling plan. Verified: `run2` declares `period_ms=1000` and executes at the sensor poll period instead. The generated firmware silently contradicts the approved sequence, and `period_ms` is exactly the field the Operations Checker validates in `check_timing_bounds` — so we validate a number we then discard.
- **Change:** Give the interpreter a real notion of elapsed time. Minimum viable and consistent with the existing `timerfd`/monotonic style in `task_sensor_poll.c`:
  1. Emit per-step state in `ops_interpreter.c`: a static array of `{ const char *step_id; unsigned period_ms; uint64_t next_due_ms; }`.
  2. Add a `static uint64_t now_ms(void)` helper using `clock_gettime(CLOCK_MONOTONIC, ...)`.
  3. `ops_runtime_on_poll_tick()` iterates the table and only runs a step when `now_ms() >= next_due_ms`, then advances `next_due_ms += period_ms` (catching up rather than drifting).
  4. Emit a `#warning`-free compile-time guard: if any step's `period_ms` is less than `SENSOR_POLL_PERIOD_MS`, the tick cannot honor it. Detect this in Python and either raise a `FirmwareEngineerError` or emit a comment plus a `fidelity_note` in the result message. Do not silently round.
- **Done when:** a test asserts `runtime/ops_interpreter.c` contains the declared `1000` for `run2` and a `now_ms`/`CLOCK_MONOTONIC` guard; a test asserts that a step whose `period_ms` is below the sensor poll period is reported (raise or degrade note), not silently accepted.

### 1.3 The interpreter never invokes `hal_call` — it only prints the description — **HIGH**

- **Files:** `templates.py` (`ops_interpreter_c`), `operations_runtime.py`
- **Why:** `RuntimePeriodicStep.hal_call` is captured and discarded; the emitted body is a single `printf`. Horizon B's own acceptance criterion in `docs/ROADMAP.md` is *"Recurring / non-boot steps map to tasks or state machine."* A `printf` of the step description is not a mapping — it is a log line that makes the firmware *look* like it implements the sequence. This is the single biggest gap between what the branch claims and what it does, and `docs/architecture/OPERATIONS_SEQUENCE.md` now lists it as "Shipped" (see 3.6).
- **Change:** Bind `hal_call` to real emitted code, and refuse to pretend when you cannot:
  1. `hal_call` is a *semantic* string (e.g. `hal_power_enable()`), not a guaranteed symbol. Resolve it against the emitted HAL modules: for a step with `target_node_id`, the module is `hal_<node_id>`; build a map of `{semantic name → emitted symbol}` from the same source `classifier`/`emitter` uses for `hal_module`, and only emit a call when the symbol is one this codegen actually generated.
  2. When the call resolves, emit the invocation (with the existing `!= 0` error-check convention used by `hal_*_read_current_ma`), not a `printf`.
  3. When it does not resolve, emit a clearly-marked `/* UNRESOLVED hal_call: ... */` stub **and** add the step to the `FirmwareGenerationResult.message` degrade note so the operator sees it. Never emit a bare `printf` that reads as if the step ran.
- **Done when:** a test with a step bound to a generated sensor module asserts the emitted `.c` contains the real HAL symbol; a test with an unresolvable `hal_call` asserts the `UNRESOLVED` marker **and** a degrade note in `result.message`.

### 1.4 Non-boot one-shot delays still run exactly once — the bug the deleted docstring described — **HIGH**

- **Files:** `operations_runtime.py` (`RuntimePlan.startup_delays`), `templates.py` (`task_operations_runtime_c`), and the docstring deleted from `emitter.py`
- **Why:** `main`'s `_boot_delays_from_operations` carried a deliberate 8-line docstring explaining that a non-boot one-shot delay (*"pause before reversing motor direction"*, an estop-release delay) *"describes a runtime pause that recurs during normal operation — baking it into main()'s one-time startup sequence would execute it once at boot and never again, silently producing firmware that does not match the operations sequence."* This branch deleted that docstring and then reproduced the exact behavior it warned about: those steps are now collected into `RuntimePlan.startup_delays`, and `task_operations_runtime` calls `ops_runtime_run_startup_sequence()` once at thread start and returns. The delay still executes once and never again. The only thing that changed is which thread it happens on. The name `startup_delays` actively obscures this — these are the steps that are *not* startup.
- **Change:**
  1. Rename `startup_delays` → `unscheduled_delays` (or `deferred_delays`) and `RuntimeDelayStep` accordingly, so the field name states what it holds: non-boot one-shot delays with no declared period.
  2. Restore the deleted rationale as a module docstring on `operations_runtime.py`, updated for the new structure. It is the highest-value comment in this subsystem and it should not have been dropped in a refactor.
  3. Decide and document the semantic. A one-shot delay with no period and no trigger condition is under-specified: it is either (a) part of a sequence that needs `depends_on` ordering (see 1.7), or (b) a step that should have been flagged `needs_refinement` by the refiner. Recommended: do **not** emit these as a fire-once thread. Instead surface them in `FirmwareGenerationResult.message` as a degrade note ("N step(s) have one-shot delays with no period or trigger — not represented in runtime firmware") and drop `task_operations_runtime.c` entirely until 1.7 gives it real sequencing.
- **Done when:** either the fire-once thread is gone and a degrade note names the affected step ids, or `task_operations_runtime` genuinely re-runs the sequence and a test proves the loop exists. Either way, a test asserts the operator is told, and the `operations_runtime.py` module docstring explains the boot/runtime distinction.

### 1.5 Periodic steps silently never execute when the project has no sensor-poll task — **HIGH**

- **Files:** `emitter.py` (`generate_source_files`), `templates.py` (`task_sensor_poll_c`)
- **Why:** `ops_runtime_on_poll_tick()` is called from exactly one place: inside `task_sensor_poll`'s loop. `main.c` only spawns that thread when the scheduling plan contains a `task_sensor_poll` task, which requires sensor nodes. A project with actuators and no sensors, or a sequence whose periodic steps have nothing to do with sensor polling, generates `runtime/ops_interpreter.c` with a fully populated `ops_runtime_on_poll_tick()` that is **never called** — no error, no warning, `success: true`. Piggybacking the operations clock on the sensor poll loop also couples two unrelated periods (1.2).
- **Change:** Give the runtime its own thread and its own timer. `task_operations_runtime.c` should own a `timerfd` at the GCD (or minimum) of the declared `period_ms` values — mirroring the `timerfd_create(CLOCK_MONOTONIC, ...)` + `read()` pattern already in `task_sensor_poll_c`, including its `read() < 0 → continue` handling — and call `ops_runtime_on_poll_tick()` itself. Then remove the `include_runtime_tick` hook from `task_sensor_poll_c` and the `#include "../runtime/ops_interpreter.h"` it injects. Spawn the thread whenever `plan.has_runtime_work` (which also fixes 1.6).
- **Done when:** a test generates firmware for a project with **no** sensor nodes plus a periodic operations step and asserts (a) `task_operations_runtime` is spawned in `main.c`, and (b) `task_sensor_poll.c` contains no `ops_runtime_` reference.

### 1.6 `task_operations_runtime.c` is compiled and linked but never spawned for periodic-only sequences — **MEDIUM**

- **Files:** `emitter.py`, `templates.py` (`main_c`, `makefile`)
- **Why:** Emission is gated on `runtime_plan.has_runtime_work` (startup **or** periodic), but the spawn is gated on `spawn_operations_runtime=runtime_plan.startup_delays` (startup only). Verified with a periodic-only sequence: `tasks/task_operations_runtime.c` is emitted, appears in `OBJS`, compiles, and links into the binary — while `main.c` contains no reference to it. Dead code shipped to hardware. `-Wall -Wextra` cannot catch it because the function has external linkage.
- **Change:** Fixing 1.5 removes the divergence (one gate, `has_runtime_work`). Separately, replace `spawn_operations_runtime: list | None` with a `bool` — it is only ever used for truthiness, and typing it as a bare `list` defeats the type checker.
- **Done when:** a test asserts that for every combination of empty/non-empty plan buckets, `tasks/task_operations_runtime.o ∈ Makefile OBJS ⟺ task_operations_runtime is spawned in main.c`.

### 1.7 `depends_on` and `condition` are silently dropped — **MEDIUM**

- **Files:** `operations_runtime.py`
- **Why:** `OperationStep.depends_on` and `OperationStep.condition` are never read. Steps are emitted in list order, so a sequence whose `depends_on` graph disagrees with array order generates out-of-order firmware. The Operations Checker specifically validates `depends_on` integrity and cycle-freedom (`check_dependency_integrity`, fatal severity) — we validate the graph, then ignore it. `condition` (e.g. *"estop released"*) is a safety guard; dropping it without a word is the most dangerous silent omission in the set.
- **Change:**
  1. Topologically sort steps by `depends_on` before partitioning (the checker already guarantees acyclicity; on a cycle, raise `FirmwareEngineerError` rather than trusting the input).
  2. For `condition`, do not attempt natural-language translation. Detect it and refuse or degrade: any step with a non-null `condition` reaching runtime emission must either block `executable` fidelity (extend the 2.6 gate) or emit an `/* UNIMPLEMENTED condition: ... */` marker and add a degrade note naming the step ids.
- **Done when:** a test with `depends_on` reversed relative to array order asserts emitted order follows the graph; a test with a `condition` asserts a degrade note or a raise, and never a silently-executed step.

### 1.8 Hardcoded `period_ms or 20` default — **LOW**

- **Files:** `operations_runtime.py`
- **Why:** A bare `20` invents a 50 Hz cadence with no provenance. Every other timing number in this codebase comes from `best_practices.py` or a manifest's `OperationalConstraints`, and `TimingConstraint.source` exists precisely to track provenance.
- **Change:** Do not synthesize a period. A step with `hal_call` and no `period_ms` is under-specified — route it to the same "tell the operator" path as 1.4, or pull a named constant from `best_practices.py` (e.g. `DEFAULT_RUNTIME_STEP_PERIOD_MS`) with a comment on where the number comes from.
- **Done when:** no numeric literal periods remain in `operations_runtime.py`; a test asserts a `hal_call`-only step is either reported or given a documented named default.

### 1.9 Step descriptions are interpolated into `printf` **format strings** — **BLOCKER**

- **Files:** `templates.py` (`ops_interpreter_c`, and `main_c`'s boot lines, which have the same exposure)
- **Why:** `ops_interpreter_c` sanitizes exactly one character: `description.replace('"', "'")`. The result is then interpolated directly into the *format string* position of a `printf`. Step descriptions are user- and LLM-authored free text arriving from the UI and from `refine_operations`, so `%`, `\`, and newlines are entirely expected in them. Confirmed with a step described as `Ramp to 100% then log %s and %d values` and another as `Wait for path C:\dev\estop release`:

```
runtime/ops_interpreter.c:14:52: error: format '%s' expects a matching 'char *' argument [-Werror=format=]
runtime/ops_interpreter.c:14:59: error: format '%d' expects a matching 'int' argument [-Werror=format=]
runtime/ops_interpreter.c:8:76:  error: unknown escape sequence: '\d' [-Werror]
```

  Two things make this worse than a compile break. First, the project `Makefile`'s `CFLAGS` has `-Wall -Wextra` but **not** `-Werror`, so `make` exits **0**, emits warnings a user will scroll past, and produces a working binary — which then dereferences whatever happens to be in the varargs register as a `char *` the first time that step fires. On a Pi that is a segfault in the middle of an operations sequence, or worse, arbitrary memory printed to the log. Second, no test compiles this file (3.4), so CI is silent.
- **Change:**
  1. Add one `_c_string_literal(text: str) -> str` helper in `templates.py` that escapes `\`, `"`, and newlines/tabs, and use it for **every** interpolated string — `ops_interpreter_c`'s startup and poll lines, and `main_c`'s boot delay lines. Delete the ad-hoc `replace('"', "'")`, which also silently corrupts legitimate quotes in descriptions.
  2. Never put runtime text in the format-string position. Emit `printf("[runtime] %s: %s\n", "<step_id>", "<description>")` so a stray `%` in the data can never be read as a conversion specifier, even if the escaping helper is later changed.
  3. Add `-Werror` to the generated `Makefile`'s `CFLAGS`. The repo already treats `-Werror` as the bar for emitted C (`test_firmware_compiles.py` compiles with it); the Makefile shipped to hardware should not be laxer than the test. If that is judged too strict for a user's local build, add it as a separate `make strict` target and use that target in the compile test.
- **Done when:** a test generates firmware from a sequence whose step description is `Ramp to 100% then log %s and %d, path C:\dev "quoted"`, asserts `make` succeeds, asserts per-file `-Werror` compilation succeeds, and asserts the description round-trips into the emitted source as literal text with no conversion specifiers in a format-string position.

### 1.10 Generated C contains stray blank lines — **LOW (cosmetic)**

- **Files:** `templates.py` (`ops_interpreter_c`, `task_sensor_poll_c`, `main_c`, `makefile`)
- **Why:** The `{... if cond else ""}` idiom leaves empty lines when the condition is false, and the accumulated `startup_lines`/`poll_lines` strings end in `\n` so each generated function body ends with a blank line before `}`. `main()` now has two consecutive blank lines where the ops-runtime spawn would go, and the Makefile has a blank line before and two after `{runtime_rules}`. Harmless to the compiler, but this is code humans read on a Pi.
- **Change:** Build the conditional lines as list entries and `"\n".join(filter(None, parts))`, or `.rstrip()` the accumulated blocks before interpolation. Prefer whichever keeps the templates readable; do not add a post-processing pass over emitted text.
- **Done when:** generated `main.c`, `runtime/ops_interpreter.c`, and `Makefile` contain no double blank lines and no blank line immediately before a closing brace.

---

## Check 2 — B2 fidelity gates and B4 orchestration endpoint

### 2.1 `POST /pipeline/run` trusts client-supplied approval flags instead of persisted metadata — **HIGH**

- **Files:** `src/eda_platform/api/routes/orchestration.py`, `src/eda_platform/orchestration/pipeline.py`, `src/eda_platform/api/schemas.py`
- **Why:** `PipelineRunRequest.schematic_approved` / `operations_approved` are booleans supplied by the caller, and `run_staged_pipeline` passes `approved=True` straight through to `generate_firmware`, hardcoded. Horizon A's whole point was making `projects/<id>/metadata.json` the authoritative record of approval — `PUT /schematic` revokes it, `POST /operations/approve` grants it, and the UI hydrates from it. This new endpoint bypasses that record entirely: any client that posts `schematic_approved: true` generates firmware, regardless of what the project's metadata says. `/firmware/generate` has the same shape, so this is not a regression — but B4 is the endpoint being positioned as *the* one-call pipeline, and it should be the one that gets this right.
- **Change:**
  1. Load the persisted metadata: `metadata = load_project_metadata(body.project_state.project_id)` and use `metadata.schematic_approved` / `metadata.operations_approved` as the source of truth.
  2. Keep the request booleans only as an explicit *opt-in override* for local/testing use, renamed to make that obvious (e.g. `allow_unapproved: bool = False`), and have the response's stage list say which source was used.
  3. Stop hardcoding `approved=True` into `generate_firmware`; pass the resolved value so the runner's defense-in-depth check stays meaningful.
- **Done when:** a test with `metadata.schematic_approved = False` on disk and `schematic_approved: true` in the body **fails** the schematic-approve stage; a test with approvals true on disk and no booleans in the body succeeds.

### 2.2 B4 has no refine stage, but the roadmap says it does — **HIGH (accuracy)**

- **Files:** `pipeline.py` (`run_staged_pipeline`), `docs/ROADMAP.md`
- **Why:** `docs/ROADMAP.md` defines B4 as *"Single staged run: validate schematic → **refine**/validate ops → generate"* and this branch marks it **Done**. `run_staged_pipeline` never calls `run_operations_refine`; `PipelineStage.OPERATIONS_REFINE` is declared and unused by the new code path. A reader of the roadmap will believe `/pipeline/run` refines. It does not.
- **Change:** Either implement it or scope it down honestly — do not leave the roadmap overstating the code.
  - *Implement:* add `refine: bool = False` to the request; when set, run `run_operations_refine` before validation, append the `OPERATIONS_REFINE` stage with its `steps_bound`/fidelity-promotion message, and feed the refined sequence forward. Note that `run_operations_refine(persist=True)` writes to disk — make persistence explicit in the request and default it to `False` for a read-only pipeline call.
  - *Scope down:* change the roadmap row to "validate schematic → validate ops → generate" and note refine is a separate call.
- **Done when:** the ROADMAP B4 row and the implementation describe the same stages, and a test asserts the exact stage sequence returned for each request shape.

### 2.3 The pipeline never loads the persisted operations master — the ops gate is skippable by omission — **HIGH**

- **Files:** `pipeline.py` (`run_staged_pipeline`), `routes/orchestration.py`
- **Why:** When `operations is None`, the pipeline skips operations validation *and* the operations-approval gate, then generates firmware. A project with an approved operations master on disk gets firmware with no runtime operations and no warning — and a caller who wants to dodge the operations gate just omits the field. Contrast `merge_operations`, which loads `project_state` from disk when omitted; the convention already exists in this module.
- **Change:** When `operations is None`, call `load_operations_master(project_id)`. If a master exists, use it and run the full gate chain. Only skip the operations stages when the project genuinely has no master, and say so in that stage's message ("no operations master on disk — firmware generated from schematic only").
- **Done when:** a test on a project with an approved master and no `operations` in the body asserts the operations stages ran and the emitted firmware includes the runtime files; a test on a project with no master asserts the skip message.

### 2.4 Approval failures return HTTP 200 with `success: false`, unlike every other route — **MEDIUM**

- **Files:** `routes/orchestration.py`
- **Why:** `/firmware/generate` returns **400** for an unapproved schematic and **422** for a `FirmwareEngineerError`; `/operations/merge` returns **422** on validation failure. `/pipeline/run` returns **200** for all of these, with the outcome buried in `success` and `stages`. Clients that check status codes — including anything generic in front of this API — will read a blocked pipeline as a successful one.
- **Change:** Pick one contract and document it in `docs/architecture/API.md`. Recommended: keep 200 for a *completed run that legitimately stopped at a gate* (that is real information the stage list conveys well), but return **422** when the request itself is unusable, and make the distinction explicit in the API doc's `/pipeline/run` row rather than leaving it implied. If you instead choose to mirror `/firmware/generate`, raise `HTTPException(422, detail=result.message)` with the stage list in the detail payload so callers keep the diagnostic.
- **Done when:** `docs/architecture/API.md` states which conditions yield 200 vs 4xx for `/pipeline/run`, and tests cover one of each.

### 2.5 `run_staged_pipeline(schematic_approved=True)` defaults to approved — **MEDIUM**

- **Files:** `pipeline.py`
- **Why:** A safety gate whose default is "gate passed" is backwards. The API layer happens to mark the field required (`Field(...)`), so today the default is unreachable through HTTP — but the function is exported from `orchestration/__init__.py` as public API, and the next caller who omits the kwarg silently gets approval-bypassed firmware.
- **Change:** Default both approval parameters to `False`, or drop them entirely once 2.1 makes metadata authoritative.
- **Done when:** `run_staged_pipeline(project, manifests)` with no keyword arguments does not generate firmware.

### 2.6 The B2 gate is silent about open questions below `executable` fidelity — **MEDIUM**

- **Files:** `src/eda_platform/agents/firmware_engineer/runner.py`
- **Why:** `fidelity_note` counts only `needs_refinement` steps. A `timed` sequence with three unresolved `open_questions` generates firmware with a completely clean success message. The roadmap's B2 criterion is *"Refuse **or degrade** codegen when open questions block `executable`"* — refuse is implemented, degrade is not. The Operations Checker's `check_open_questions` rule already treats unresolved questions as blocking promotion, so codegen is quieter than validation.
- **Change:** Extend the degrade note to cover both signals, and name them separately so the operator knows which: `"(degraded: N step(s) need refinement; M open question(s) unresolved)"`. Build the note from a small helper so the counts and wording live in one place.
- **Done when:** a test asserts a `timed` sequence with open questions produces a `result.message` naming the open-question count, and still succeeds.

### 2.7 Duplicated fidelity branches; gate logic diverges from the checker — **LOW**

- **Files:** `runner.py`
- **Why:** Two consecutive `if operations.fidelity == FidelityLevel.EXECUTABLE:` blocks, and the conditions are re-derived here rather than reusing `validate_operations_collect`'s `check_open_questions` / refinement rules. Two implementations of "is this sequence ready" will drift.
- **Change:** Collapse into one `if operations.fidelity is FidelityLevel.EXECUTABLE:` block with both checks inside, and factor the readiness predicate into a single function (in `operations_checker`, imported by the runner) so codegen and validation share one definition.
- **Done when:** one fidelity branch remains, and the readiness rule has exactly one implementation.

### 2.8 Pipeline tests write firmware into the repository tree — **MEDIUM (regression against Horizon A 1.4)**

- **Files:** `tests/api/test_pipeline.py`, `routes/orchestration.py`, `tests/conftest.py`
- **Why:** `test_pipeline_run_success` posts to the live route, which calls `run_staged_pipeline` without `output_root`, so it writes `generated/firmware/valid_i2c_wiring/` inside the checkout. Confirmed present after a test run. `tests/conftest.py` redirects `_PROJECTS_DIR` and `_DATASHEETS_DIR` but not the firmware output root, and `generated/firmware/*/` is gitignored, so `git status` stays clean and the pollution is invisible — which is exactly why Horizon A item 1.4 asked for tests that touch no repo paths at all.
- **Change:** Extend the autouse fixture in `tests/conftest.py` to monkeypatch `eda_platform.agents.firmware_engineer.runner._DEFAULT_OUTPUT_ROOT` to a `tmp_path_factory` directory. That covers every route-level test that reaches codegen, not just this one. Keep the explicit `output_root=tmp_path` in direct-call tests.
- **Done when:** `rm -rf generated/firmware/*` then `pytest -q` leaves `generated/firmware/` containing nothing but `.gitkeep`. Check the directory listing, not `git status` — `generated/firmware/*/` is gitignored, so a dirty tree here is invisible to git by design.

---

## Check 3 — B3 UI, test coverage, documentation accuracy

### 3.1 Doc previews are never cleared on project switch or canvas edit — **HIGH**

- **Files:** `ui/src/store/useSchematicStore.ts`
- **Why:** `operatingProcedureMd` / `bringupChecklistMd` are cleared in exactly one place: the start of `generateFirmwareForProject`. They are **not** cleared by `resetApprovalAndFirmware()`, `resetWorkflowState()`, or the explicit reset block in `loadProject` — 11 call sites covering node edits, edge edits, project load, project switch, and new-project creation. Result: switch from project A to project B and B's panel shows A's operating procedure and bring-up checklist next to an `idle` firmware status. Delete a node and the stale docs stay on screen while approval is revoked. This is the same stale-cross-project-state class as Horizon A items 2.1–2.3, reintroduced.
- **Change:** Move the two fields into `resetApprovalAndFirmware()` so every existing reset path picks them up automatically, and delete the now-redundant explicit clears in `loadProject`'s reset block (they are already covered) and in `generateFirmwareForProject` (keep that one — it clears before a new run).
- **Done when:** a vitest case loads project A, generates firmware (mocked docs), switches to project B, and asserts both doc fields are `null`; a second case asserts a node deletion clears them.

### 3.2 A failed docs fetch is swallowed with no user-visible signal — **MEDIUM**

- **Files:** `ui/src/store/useSchematicStore.ts`
- **Why:** `catch { /* docs are supplementary to firmware output */ }`. If `/operations/generate-docs` is down or 422s, the user sees firmware success and simply no docs, with nothing to distinguish "this project has no docs" from "the docs call failed". The comment justifies not failing the firmware result — correct — but not staying silent.
- **Change:** Track the outcome and surface it. Add a `docsMessage: string | null` (or append to `firmwareMessage`, e.g. `"… — operating docs unavailable: <reason>"`) and render it in `ValidationPanel` where the previews would be. Fetch the two docs alongside the firmware result rather than strictly after, so a slow docs call does not delay the success state.
- **Done when:** a vitest case with `generateOperatingDocs` rejecting asserts `firmwareStatus === "success"` **and** a non-null user-facing message mentioning docs.

### 3.3 B3 ships with zero new UI tests — **MEDIUM**

- **Files:** `ui/src/store/useSchematicStore.test.ts` (or a new `useSchematicStore.docs.test.ts`)
- **Why:** The `vitest` count is unchanged at 33 across the branch. B3 added a new API client function, a new store fetch path, two new store fields, prop plumbing through `SchematicEditor`, and new markup in `ValidationPanel` — none of it exercised. 3.1 and 3.2 are both defects a single test would have caught.
- **Change:** Add cases to the existing store test file (it already mocks `@/lib/api`): docs populated on firmware success with operations present; docs left null when there is no active operations sequence; docs cleared on the reset paths (3.1); failure path (3.2).
- **Done when:** the four cases exist and pass, and each one fails if its corresponding fix is reverted.

### 3.4 None of the new generated C is ever compiled by a test — **HIGH**

- **Files:** `tests/agents/test_firmware_compiles.py`
- **Why:** `tests/agents/test_firmware_compiles.py` exists specifically for this. Its docstring says it targets *"the class of bug that unit tests over the generator can't catch"* and names a real `-Wunused-result` escape as the motivating regression. Both of its tests call `generate_firmware` **without** `operations`, so `runtime/ops_interpreter.c` and `tasks/task_operations_runtime.c` — roughly 90 lines of new emitted C — are never handed to a compiler in CI. This gap is not hypothetical: it is what allowed 1.9 to ship. With a benign sequence the runtime tree compiles clean under `-Wall -Wextra -Werror` (verified manually: 7/7 files, `make` links); with a `%` in a step description it does not, and nothing in CI notices.
- **Change:**
  1. Parametrize both existing compile tests over `operations=None` and a runtime-ops sequence, so `make` + per-file `-Werror` cover the runtime tree in both configurations.
  2. Add the hostile-description case from 1.9 as a third parametrization.
  3. Fix the escaping itself under 1.9 — do not merely add the test.
- **Done when:** the compile tests run in all three configurations, and reverting the 1.9 escaping fix turns the hostile-description case red.

### 3.5 Unit coverage is one test per horizon item and misses every branch above — **HIGH**

- **Files:** `tests/agents/test_operations_runtime.py`, `tests/agents/test_firmware_fidelity_gates.py`, `tests/api/test_pipeline.py`
- **Why:** B1 gets one test (boot vs runtime delay partition, which passes *because* it uses a step with no `hal_call` — swap in a `hal_call` and it exposes 1.1). B2 gets one test (open questions) and never touches the `needs_refinement` gate or the degrade note it added. B4 gets two tests, neither of which involves operations at all, so the entire operations gate chain in the new endpoint is unexercised. `RuntimePlan.periodic_steps`, `has_runtime_work`, and the `period_ms or 20` default have no tests whatsoever.
- **Change:** Add, at minimum:
  - `build_runtime_plan`: periodic partition; `hal_call`-only step; boot step *with* `hal_call` (1.1); step with both `delay_ms` and `period_ms`; `has_runtime_work` true/false; partition-ness property test (1.1).
  - Fidelity gates: `needs_refinement` blocks `executable`; `needs_refinement` below `executable` yields the degrade note; open questions below `executable` yield a note (2.6).
  - Pipeline: ops validation failure stops the run; ops present but unapproved stops the run; approved ops produce runtime files; metadata-vs-body approval precedence (2.1); master loaded from disk when omitted (2.3).
- **Done when:** each of the above exists, and reverting any Check 1 or Check 2 fix turns at least one test red.

### 3.6 Docs claim more than the code delivers — **MEDIUM**

- **Files:** `docs/ROADMAP.md`, `docs/architecture/OPERATIONS_SEQUENCE.md`
- **Why:** As committed, the branch marked B1–B4 **Done**, flipped `OPERATIONS_SEQUENCE.md`'s "Not yet shipped" note to three "Shipped" rows, and rewrote the baseline table to say firmware has a *"runtime ops interpreter for timed/executable sequences."* Given 1.1–1.3 and 1.9, what actually ships is a `printf` log at the wrong cadence that double-fires boot steps and crashes on a `%` character. The Horizon A review's most repeated theme was documentation asserting capability the tests did not establish; the fix there was to make the docs match the code, and that discipline did not carry over.
- **Already done in this review commit:** those rows are downgraded to "Partial" / "In review" with a pointer here, so `main`-bound docs no longer assert something false. Do not treat that as the fix — it is a holding statement.
- **Change:** After the Check 1 fixes land, rewrite the rows to describe the real capability, naming the limits explicitly — which step fields are honored (`period_ms`, `hal_call`, `depends_on`) and which are surfaced-but-unimplemented (`condition`, unperiodized one-shot delays). Promote a row to "Done" only when a named test backs it. Also update the `docs/architecture/API.md` `/pipeline/run` row for whatever 2.2 / 2.4 settle on.
- **Done when:** each "Shipped"/"Done" claim maps to a named test, and every unimplemented step field is listed as such in `OPERATIONS_SEQUENCE.md`.

### 3.7 `boot_delay_steps` docstring describes a function that no longer exists — **LOW**

- **Files:** `operations_runtime.py`
- **Why:** `"""Boot-only delays for main() (delegates to emitter helper semantics)."""` — the emitter helper was deleted in this same commit, and this function does not delegate to anything. The parenthetical points a reader at code that is gone.
- **Change:** Replace with the substance: that only `is_boot_step` descriptions belong in `main()`'s one-shot sequence, and cross-reference the runtime bucket for everything else (this is the natural home for part of the 1.4 docstring restoration).
- **Done when:** the docstring describes current behavior and names the boot/runtime split.

---

## Recommended sequencing

The Check 1 fixes are interdependent — do them as one pass, not one item at a time.

1. **Escaping and compile coverage first** (1.9, 3.4). It is a prerequisite for trusting anything else you emit, it is the cheapest item here, and it is the only one that ships a crash.
2. **Rebuild the partition and the runtime thread** (1.1, 1.4, 1.5, 1.6, 1.8, plus 1.7's topological sort). This is one coherent change to `operations_runtime.py` + `templates.py` + `emitter.py`. Land the partition-ness property test with it.
3. **Make the interpreter honor time and HAL calls** (1.2, 1.3) on top of the new thread. This is the largest single piece of work in the remediation and the one that decides whether B1 is real.
4. **Gates and orchestration** (2.1, 2.3, 2.5, 2.6, 2.7, then 2.2 and 2.4 as contract decisions). Independent of Check 1 — safe to do in parallel if you are splitting work.
5. **UI** (3.1, 3.2, 3.3). Small and self-contained.
6. **Docs last** (2.2's roadmap row, 2.4's API row, 3.6, 3.7, 1.10). Write them against what the tests prove, not against the plan.

## Verification loop for the remediation

```bash
cd /workspace
python3 -m pytest -q
rm -rf generated/firmware/* && python3 -m pytest -q && git status --porcelain   # must print nothing (2.8)
cd ui && npx tsc --noEmit && npx vitest run
cd /workspace && python3 scripts/horizon_a_verify.py --write-firmware --require-toolchain
```

`horizon_a_verify` exercises `demo_robot`, whose operations master is boot-heavy, so it will **not** catch runtime-ops regressions. Add a runtime-ops project to that script's coverage, or accept that `test_firmware_compiles.py` (3.4) is the only gate on emitted runtime C and keep it parametrized.
