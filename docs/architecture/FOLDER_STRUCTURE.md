# Repository Folder Structure

This document defines the top-level layout for the intelligent EDA and firmware code-generation platform. The structure enforces strict separation between UI, agent orchestration, hardware knowledge, and generated output so each agent can operate on well-defined JSON artifacts without tight coupling.

## Directory Tree

```
hardware-dev-project/
├── README.md
├── pyproject.toml
├── docs/
│   ├── architecture/
│   │   └── FOLDER_STRUCTURE.md       # This document
│   └── firmware/
│       └── CONCURRENCY_STRATEGY.md     # Firmware Agent threading model
│
├── src/eda_platform/                   # Core Python package
│   ├── __init__.py
│   ├── schemas/                        # Pydantic models (lingua franca)
│   │   ├── __init__.py
│   │   ├── enums.py
│   │   ├── component_manifest.py       # ComponentManifest schema
│   │   └── project_state.py            # ProjectState schema
│   ├── agents/                         # Specialized swarm agents
│   │   ├── __init__.py
│   │   ├── librarian/                  # PDF → ComponentManifest
│   │   ├── architect/                  # Intent → ProjectState layout
│   │   ├── logic_checker/              # ProjectState validation
│   │   └── firmware_engineer/          # ProjectState → HAL + firmware
│   └── orchestration/                  # Agent routing & handoff pipeline
│       └── __init__.py
│
├── hardware_library/                   # Persistent hardware knowledge base
│   ├── datasheets/                     # Source PDF datasheets (Librarian input)
│   └── manifests/                      # Validated ComponentManifest JSON files
│       ├── *.example.json              # Reference fixtures (validated by tests)
│
├── projects/                           # User project artifacts
│   ├── <project_id>/                   # Per-project ProjectState & metadata
│   └── *.example.json                  # Reference ProjectState fixtures
│
├── generated/                          # Agent output (never hand-edited)
│   └── firmware/                       # HAL + application code from Firmware Agent
│       └── <project_id>/
│
├── ui/                                 # Future web-based schematic editor (placeholder)
│   └── README.md
│
└── tests/
    └── schemas/                        # Schema validation unit tests
```

## Major Directory Responsibilities

### `src/eda_platform/schemas/`

**Purpose:** Backend data validation layer.

Defines the canonical Pydantic models for `ComponentManifest` and `ProjectState`. Every agent reads and writes JSON that must validate against these models before handoff. This is the single source of truth for inter-agent communication.

### `src/eda_platform/agents/`

**Purpose:** Agent implementations, one subdirectory per swarm role.

| Subdirectory       | Agent              | Input                         | Output              |
|--------------------|--------------------|-------------------------------|---------------------|
| `librarian/`       | Hardware Librarian | PDF datasheets                | `ComponentManifest` |
| `architect/`       | Systems Architect  | Manifests + user intent       | `ProjectState`      |
| `logic_checker/`   | Logic Checker      | `ProjectState` + manifests    | Validated state / fatal errors |
| `firmware_engineer/` | Firmware Engineer | Validated `ProjectState`    | HAL + threaded firmware |

Each agent is isolated: it receives typed JSON, performs one job, and emits typed JSON. No agent reaches into another agent's internals.

### `src/eda_platform/orchestration/`

**Purpose:** Agent Orchestration.

Coordinates the swarm pipeline: Librarian → Architect → Logic Checker → (user approval) → Firmware Engineer. Handles routing, error propagation, and state persistence between stages. Intentionally lightweight—no heavy framework until complexity demands it.

### `hardware_library/`

**Purpose:** Hardware Library.

- `datasheets/` — Raw PDF inputs scanned by the Librarian.
- `manifests/` — Parsed, validated `ComponentManifest` JSON keyed by `component_id` (e.g., `mcu_rp2040.json`). Reused across projects.

### `projects/`

**Purpose:** Per-project schematic state.

Stores `ProjectState` JSON and project metadata. The Architect writes here; the Logic Checker reads from here; the UI (future) renders from here.

### `generated/firmware/`

**Purpose:** Output Code.

Firmware Engineer writes platform-specific HAL layers and application code here, organized by `project_id`. Generated artifacts are treated as build output, not source-of-truth.

### `ui/`

**Purpose:** User Interface (future).

Placeholder for the web-based visual schematic editor. Will consume `ProjectState` for rendering and emit user edits back as updated `ProjectState`. No functional UI in the initial scaffold.

### `docs/`

**Purpose:** Architecture and design decisions.

Holds human-readable specifications (folder layout, concurrency strategy, agent directives) that govern agent behavior.

### `tests/`

**Purpose:** Automated validation.

Schema tests ensure Pydantic models enforce the JSON contracts. Agent and orchestration tests will be added as implementations land.

## Data Flow Summary

```
datasheets/  ──►  librarian  ──►  manifests/  (ComponentManifest)
                                      │
user intent ──►  architect  ──►  projects/   (ProjectState)
                                      │
                               logic_checker (validate)
                                      │
                               user approval
                                      │
                               firmware_engineer ──►  generated/firmware/
```
