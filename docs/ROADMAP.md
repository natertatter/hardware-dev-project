# Product Roadmap

Living plan for the EDA platform. **Implementation status** for the operations sequence system is recorded in [`docs/architecture/OPERATIONS_SEQUENCE.md`](architecture/OPERATIONS_SEQUENCE.md). **HTTP contracts** are in [`docs/architecture/API.md`](architecture/API.md).

Last reviewed: 2026-09-29 (Horizon C2–C3 — datasheet timing provenance in refine, and example-to-production catalog promotion. C1 vendor-PDF layout extraction remains open).

---

## Current baseline

| Area | Status | Notes |
|------|--------|--------|
| Schemas | Mature | `ComponentManifest`, `ProjectState`, `OperationsSequence`, protocols, `OperationalConstraints` |
| Logic Checker | Mature | Rule-based validation with broad test coverage |
| Systems Architect | v1 | Deterministic template auto-wire (I2C, SPI, multi-MCU UART/USB serial) |
| Hardware Librarian | v1.1 | JSON upload commits immediately. PDF text → reviewable draft (deterministic extract; Anthropic when `ANTHROPIC_API_KEY` is set). Catalog write only after human save. `*.example.json` templates promote to `{component_id}.json`. Arbitrary vendor-PDF layout extraction not yet. |
| Operations | v1 | Refiner, checker, API, UI panel, optional LLM, operating docs |
| Firmware Engineer | v1 (Pi 4) | pthreads + I2C sensors; boot delays + runtime ops interpreter for timed/executable sequences |
| UI | v1 | React Flow editor, catalog, protocols, datasheet upload, operations sidebar |
| CI / deploy | v1 | Docker Compose with `projects/` + `generated/` mounts; GitHub Actions runs `pytest` and UI `vitest` |

**North star:** datasheet → schematic → validate → behavioral operations → trustworthy firmware and runbooks, with explicit human approval gates.

---

## Horizon A — Trust the demo

**Goal:** One reference project runs UI → API → disk → firmware → Raspberry Pi 4 without hand-editing JSON.

| ID | Work | Done when |
|----|------|-----------|
| A1 | Project persistence in UI | **Done** — toolbar project selector, load/save `schematic.json`, schematic + operations approval persisted via API/metadata |
| A2 | Documentation alignment | **Done** — HOW_TO, API, Compose notes updated |
| A3 | Docker persistence | **Done** — `projects/` and `generated/` mounted in Compose |
| A4 | CI baseline | **Done** — `.github/workflows/ci.yml` |
| A5 | Pi hardware smoke | **Done** — [`docs/firmware/PI4_HARDWARE_SMOKE.md`](firmware/PI4_HARDWARE_SMOKE.md), `scripts/horizon_a_verify.py`, `scripts/pi4_on_device_smoke.sh` |

---

## Horizon B — Behavior matches wiring

**Goal:** Operations sequences at `timed` / `executable` fidelity drive **runtime** firmware, not only boot delays and markdown docs.

| ID | Work | Done when |
|----|------|-----------|
| B1 | Runtime operations interpreter | **Done** — `operations_runtime.py`, `runtime/ops_interpreter`, `task_operations_runtime` (`period_ms`, bound `hal_call`, `depends_on` order; see runtime limits in [`OPERATIONS_SEQUENCE.md`](architecture/OPERATIONS_SEQUENCE.md)) |
| B2 | Codegen fidelity gates | **Done** — refuse `executable` on open questions / `needs_refinement` / `condition`; degrade below `executable` |
| B3 | Operating docs in UI | **Done** — post-firmware `generate-docs` preview + reset on workflow change |
| B4 | Orchestration endpoint | **Done** — `POST /api/v1/pipeline/run` (metadata approvals, load master, optional `refine`) |

Senior review history: [`docs/reviews/HORIZON_B_SENIOR_REVIEW.md`](reviews/HORIZON_B_SENIOR_REVIEW.md).

---

## Horizon C — Datasheets become manifests

**Goal:** PDF upload yields reviewable manifests with pins, protocols, and datasheet-backed timing.

| ID | Work | Done when |
|----|------|-----------|
| C1 | LLM extraction pipeline | **Partial** — shipped: PDF text → `ComponentManifest` draft, validation issues (schema, protocol, defaulted fields), and a human edit/commit loop (`POST /api/v1/librarian/manifests`; UI review form). Deterministic parser covers labeled excerpts and common electrical phrases; optional Anthropic extractor when `ANTHROPIC_API_KEY` is set, with deterministic fallback. Not done: layout-aware or scanned vendor PDFs (pin tables as drawings). |
| C2 | Provenance in refine | **Done** — refine copies `power_on_delay_ms` and `conversion_time_ms` into `TimingConstraint.source` / `note` and `OperationStep.provenance` (`datasheet`). A slower scheduling poll keeps the plan period and marks provenance `inferred`. Existing step timing is left unchanged. `i2c_max_clock_hz` is not a step timing field. Contract: [`docs/reviews/HORIZON_C2_C3_PLAN.md`](reviews/HORIZON_C2_C3_PLAN.md). |
| C3 | Catalog hygiene | **Done** — `*.example.json` is not in the live catalog. `GET /api/v1/manifests/examples` lists templates; `POST /api/v1/manifests/{component_id}/promote` copies one to `{component_id}.json` (**409** if that file exists). `mcu_rp2040` and `sens_ina219` are promoted in-repo for `demo_robot`. The parts library can promote the rest. No overwrite. Contract: [`docs/reviews/HORIZON_C2_C3_PLAN.md`](reviews/HORIZON_C2_C3_PLAN.md). |
| C4 | Schema enhancements | e.g. `nominal_voltage` on `Pin` for cleaner power rules |

---

## Horizon D — Design faster than hand-wiring

**Goal:** Assisted layout with Logic Checker as the safety gate.

| ID | Work | Done when |
|----|------|-----------|
| D1 | More auto-wire templates | **Partial** — SPI auto-wire with tests is on main (PR #21). Other buses remain. |
| D2 | LLM layout suggestions | Non-authoritative proposals; validation required |
| D3 | Intent → draft schematic | NL or BOM → editable `ProjectState` |
| D4 | Logical vs deployment MCU | Clear UX for canvas MCU vs Pi 4 codegen target |

---

## Horizon E — Firmware breadth

**Goal:** Richer Pi 4 codegen, then a second target (bare metal).

| ID | Work | Done when |
|----|------|-----------|
| E1 | Motor / actuator HAL on Pi 4 | End-to-end with classifier + codegen |
| E2 | Scheduling tests | Emitted tasks match `SchedulingPlan` |
| E3 | Second platform | e.g. RP2040 + FreeRTOS emitter behind same schemas |
| E4 | Toolchain docs | Cross-compile and flash for non-Linux targets |

---

## Horizon F — Team-ready platform (later)

Authentication, multi-project tenancy, hosted deploy (TLS), pipeline observability. Intentionally deferred until Horizons A–B are solid.

---

## Suggested order

1. ~~**A1, A4, A2** (persistence, CI, docs)~~ — complete
2. ~~**A5** (hardware proof)~~ — host script + Pi checklist complete
3. ~~**B1–B4** (executable ops + docs UX + pipeline)~~ — complete
4. **C1** (Librarian v2) — partial: text extract + validate + human commit shipped; arbitrary vendor-PDF / scanned-page extraction remains
5. **C2** (provenance in refine) — complete for `power_on_delay_ms` and `conversion_time_ms`
6. **C3** (catalog hygiene) — complete: promote `*.example.json` to production `{id}.json`; no overwrite
7. **E1** (motors on Pi)
8. **D2 / D3**, then **E3**

---

## Success metrics

| Metric | Target |
|--------|--------|
| Time to first firmware | New contributor: documented path to `generated/firmware/` in one session |
| Regressions | PRs blocked on failing automated tests |
| Behavioral fidelity | Reference project: validated ops reflected in firmware for defined scenarios |
| Hardware | At least one Pi 4 smoke path documented |

---

## Non-goals (for now)

- Production SaaS, billing, multi-user auth
- Full ECAD tool import/export parity
- Autonomous approve-and-ship without human gates
- Every MCU family before Pi 4 + one bare-metal target is proven
