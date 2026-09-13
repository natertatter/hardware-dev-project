# Product Roadmap

Living plan for the EDA platform. **Implementation status** for the operations sequence system is recorded in [`docs/architecture/OPERATIONS_SEQUENCE.md`](architecture/OPERATIONS_SEQUENCE.md). **HTTP contracts** are in [`docs/architecture/API.md`](architecture/API.md).

Last reviewed: 2026-09-13 (Horizon B senior review — first implementation not yet accepted; see [`docs/reviews/HORIZON_B_SENIOR_REVIEW.md`](reviews/HORIZON_B_SENIOR_REVIEW.md)).

---

## Current baseline

| Area | Status | Notes |
|------|--------|--------|
| Schemas | Mature | `ComponentManifest`, `ProjectState`, `OperationsSequence`, protocols, `OperationalConstraints` |
| Logic Checker | Mature | Rule-based validation with broad test coverage |
| Systems Architect | v1 | Deterministic template auto-wire (I2C bus, multi-MCU UART/USB serial) |
| Hardware Librarian | v1 | Upload JSON or PDF; PDF → template manifest (full LLM extraction not yet) |
| Operations | v1 | Refiner, checker, API, UI panel, optional LLM, operating docs |
| Firmware Engineer | v1 (Pi 4) | pthreads + I2C sensors; boot delays from operations; runtime ops interpreter in review (Horizon B) |
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

**Status: in review.** First implementation is on `cursor/horizon-b-be2c` (PR #16) and is **not** accepted — see [`docs/reviews/HORIZON_B_SENIOR_REVIEW.md`](reviews/HORIZON_B_SENIOR_REVIEW.md) for the blocking defects.

| ID | Work | Done when |
|----|------|-----------|
| B1 | Runtime operations interpreter | **Partial** — `operations_runtime.py` + emitted `runtime/ops_interpreter`, but `period_ms`, `hal_call`, `depends_on`, and `condition` are not yet honored |
| B2 | Codegen fidelity gates | **Partial** — `runner.py` refuses `executable` on open questions / `needs_refinement`; degrade path incomplete |
| B3 | Operating docs in UI | **Partial** — post-firmware `generate-docs` preview in Validation panel; previews go stale across projects |
| B4 | Orchestration endpoint | **Partial** — `POST /api/v1/pipeline/run`; no refine stage, and approval gates do not consult project metadata |

---

## Horizon C — Datasheets become manifests

**Goal:** PDF upload yields reviewable manifests with pins, protocols, and datasheet-backed timing.

| ID | Work | Done when |
|----|------|-----------|
| C1 | LLM extraction pipeline | Structured extract + validate + human edit loop |
| C2 | Provenance in refine | Timing fields flow from manifest into operations provenance |
| C3 | Catalog hygiene | Clear promotion path from `.example.json` to production manifests |
| C4 | Schema enhancements | e.g. `nominal_voltage` on `Pin` for cleaner power rules |

---

## Horizon D — Design faster than hand-wiring

**Goal:** Assisted layout with Logic Checker as the safety gate.

| ID | Work | Done when |
|----|------|-----------|
| D1 | More auto-wire templates | SPI and other buses with tests |
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
3. **B1–B4** — first pass implemented, remediation pending senior review
4. **C1** (Librarian v2)
5. **E1** (motors on Pi)
6. **D2 / D3**, then **E3**

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
