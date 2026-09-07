# Operations Sequence System — Implementation Plan

This document defines how the platform implements **progressive-fidelity operations sequences**: light vibe input → refined steps → master artifact → firmware and operating documents.

## Goals

1. Capture behavioral intent alongside electrical `ProjectState` (what the system does, not just how it is wired).
2. Support **light → heavy** fidelity without a hard format migration.
3. Refine vibe/draft input using datasheet knowledge, electrical architecture, and domain best practices.
4. Validate refined operations against schematic reality before firmware generation.
5. Preserve open questions as first-class artifacts for iterative Cursor sessions.

## Artifact Layout

```
projects/
└── <project_id>/
    ├── schematic.json              # ProjectState (approved schematic)
    ├── metadata.json               # approval flags, fidelity stage, timestamps
    └── operations/
        ├── master.json             # canonical operations sequence (grows over time)
        ├── drafts/
        │   └── draft_<timestamp>.json
        └── refined/
            └── refined_<version>.json
```

## Schema Model

### Fidelity levels

| Level | Enum | Content | Validated by |
|-------|------|---------|--------------|
| 0 | `narrative` | Prose + coarse steps | Refiner suggests structure |
| 1 | `steps` | Ordered steps, optional node binding | Checker: node references |
| 2 | `timed` | Explicit delays/periods with provenance | Checker: timing vs manifests + scheduling |
| 3 | `executable` | HAL calls, tiers, conditions | Firmware Engineer consumes |

Steps may sit at different effective fidelity within one sequence via `needs_refinement` and `open_questions`.

### Core types (`src/eda_platform/schemas/operations_sequence.py`)

- `OperationsSequence` — project_id, fidelity, version, steps, open_questions, optional narrative
- `OperationStep` — step_id, description, target_node_id, hal_call, tier, timing, depends_on, provenance
- `OpenQuestion` — question_id, related_step_id, text
- `TimingConstraint` — delay_ms, period_ms, source (human | datasheet | best_practice | inferred)
- `ProjectMetadata` — schematic_approved, operations_approved, operations_fidelity

## Agent Pipeline

```
Vibe/draft input
    → Operations Refiner (bind nodes, add timing, promote fidelity, surface questions)
    → Operations Checker (cross-check vs ProjectState, manifests, scheduling plan)
    → Refined output (for human review)
    → Merge into master.json (on approval)
    → Firmware Engineer (future: embed executable ops in generated code)
```

### Operations Refiner (`src/eda_platform/agents/operations_refiner/`)

**Inputs:** `OperationsSequence` (narrative/steps) + `ProjectState` + manifests

**Responsibilities:**
- Match step descriptions to `ProjectState.nodes` via component_id / manifest name keywords
- Assign `hal_module` and `ExecutionTier` via firmware `classifier`
- Inject timing from `best_practices.py` (I2C poll period, power-on delay, motor ramp)
- Promote fidelity one level (narrative → steps → timed; timed → executable when fully bound)
- Emit `OpenQuestion` for ambiguous bindings or missing electrical prerequisites

**Output:** `RefineResult` with refined `OperationsSequence`, warnings, and questions

### Operations Checker (`src/eda_platform/agents/operations_checker/`)

Mirrors Logic Checker pattern: individual rules + `validate_operations_collect()`.

**Rules (v1):**
| Rule | Severity | Description |
|------|----------|-------------|
| `check_node_references` | fatal | `target_node_id` must exist in ProjectState |
| `check_dependency_integrity` | fatal | `depends_on` references valid step_ids, no cycles |
| `check_hal_binding` | warning | `hal_call` should match node's HAL module when set |
| `check_timing_bounds` | warning | period_ms below scheduling plan minimum |
| `check_boot_order` | warning | sensor/actuator steps before power-rail enable |
| `check_open_questions` | warning | unresolved questions block promotion to executable |

**Precondition:** schematic should pass Logic Checker; checker emits warning if not.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/projects/{id}/operations/master` | Load master sequence |
| PUT | `/api/v1/projects/{id}/operations/master` | Save intent-level master |
| POST | `/api/v1/projects/{id}/operations/drafts` | Append vibe/draft capture |
| POST | `/api/v1/operations/refine` | Refine sequence against ProjectState |
| POST | `/api/v1/operations/validate` | Validate refined sequence |
| POST | `/api/v1/operations/merge` | Promote refined → master (with version bump) |

## Orchestration (`src/eda_platform/orchestration/pipeline.py`)

```python
class PipelineStage(str, Enum):
    SCHEMATIC_VALIDATE = "schematic_validate"
    SCHEMATIC_APPROVE = "schematic_approve"
    OPERATIONS_REFINE = "operations_refine"
    OPERATIONS_VALIDATE = "operations_validate"
    OPERATIONS_APPROVE = "operations_approve"
    FIRMWARE_GENERATE = "firmware_generate"
```

Extended flow:

```
Architect → Logic Checker → [Approve Schematic]
    → Operations Refiner → Operations Checker → [Approve Operations]
    → Firmware Engineer
```

Gate firmware on `metadata.schematic_approved` (existing) and optionally `metadata.operations_approved` (future phase).

## Implementation Phases

### Phase 1 — Foundation (this PR)

- [x] Pydantic schemas with fidelity levels
- [x] Project loader (read/write master, drafts, refined, metadata)
- [x] Operations Refiner (deterministic binding + best-practice timing)
- [x] Operations Checker (structural + electrical cross-check rules)
- [x] API routes for refine/validate/load/save/merge
- [x] Orchestration pipeline skeleton
- [x] Example fixtures: `projects/demo_robot/operations/`
- [x] Unit + API tests

### Phase 2 — UI integration

- Operations editor panel (fidelity badge, refine/validate/approve buttons)
- Extend `useSchematicStore` or add `useOperationsStore`
- TypeScript types mirroring backend schemas
- Draft capture from natural-language input field

### Phase 3 — Librarian enrichment

- Extract operational constraints from datasheets into manifest extensions:
  - `power_on_delay_ms`, `conversion_time_ms`, `i2c_max_clock_hz`
- Refiner reads manifest timing fields instead of only best-practice defaults

### Phase 4 — Firmware + operating docs

- Firmware Engineer consumes `executable` fidelity steps
- Generate `OPERATING_PROCEDURE.md`, `BRINGUP_CHECKLIST.md` from master sequence
- Dual approval gate: schematic + operations before codegen

### Phase 5 — LLM-assisted refinement

- Provider abstraction (Anthropic BYOK) for vibe → structured step parsing
- Question-asking loop in refiner for ambiguous intent
- Provenance tagging on inferred timings

## Cursor Workflow (end-to-end)

1. **Ingest:** Upload PDFs → Librarian manifests → commit to `hardware_library/`
2. **Design:** Place/wire schematic → validate → approve → save `schematic.json`
3. **Capture vibe:** Add draft via API or PUT master with narrative fidelity
4. **Refine:** `POST /operations/refine` → review `refined/` output and open questions
5. **Validate:** `POST /operations/validate` → fix errors, answer questions
6. **Merge:** `POST /operations/merge` → promote to master, bump version
7. **Generate:** Approve operations → firmware + operating docs (Phase 4)

## Design Principles

1. **Append-friendly master** — refinement produces diffs; merge is explicit
2. **Questions are first-class** — block executable promotion, not whole project
3. **Provenance on every timing** — datasheet vs best-practice vs human procedure
4. **Same approval pattern as wiring** — validate → approve → generate
5. **Checker severity levels** — fatal (impossible), warning (best practice), question (needs human)
