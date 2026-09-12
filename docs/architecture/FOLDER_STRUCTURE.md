# Repository Folder Structure

Top-level layout for the intelligent EDA and firmware code-generation platform. UI, agents, hardware knowledge, and generated output stay separated so each stage operates on well-defined JSON artifacts.

**Related docs:** [`API.md`](API.md), [`OPERATIONS_SEQUENCE.md`](OPERATIONS_SEQUENCE.md), [`ROADMAP.md`](../ROADMAP.md), [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md).

## Directory Tree

```
hardware-dev-project/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── docs/
│   ├── HOW_TO.md
│   ├── ROADMAP.md
│   ├── architecture/
│   │   ├── API.md
│   │   ├── ENGINEERING_DECISIONS.md
│   │   ├── FOLDER_STRUCTURE.md
│   │   └── OPERATIONS_SEQUENCE.md
│   └── firmware/
│       └── CONCURRENCY_STRATEGY.md
│
├── src/eda_platform/
│   ├── schemas/                        # Pydantic lingua franca
│   ├── agents/                         # Librarian, Architect, Logic Checker,
│   │                                   # Operations Refiner/Checker, Firmware Engineer
│   ├── api/                            # FastAPI routes, project_loader, manifest_loader
│   ├── llm/                            # Optional LLM provider (BYOK)
│   └── orchestration/                  # Pipeline stage helpers
│
├── hardware_library/
│   ├── datasheets/                     # PDF inputs (Librarian)
│   └── manifests/                      # ComponentManifest JSON (*.json, *.example.json)
│
├── projects/
│   └── <project_id>/
│       ├── schematic.json              # ProjectState
│       ├── metadata.json               # Approval flags, operations fidelity
│       └── operations/
│           ├── master.json
│           ├── drafts/
│           └── refined/
│
├── generated/firmware/<project_id>/    # Build output (gitignored)
│
├── ui/                                 # Next.js + React Flow schematic editor
│
└── tests/                              # pytest (schemas, agents, API)
```

## Major directory responsibilities

### `src/eda_platform/schemas/`

Canonical Pydantic models: `ComponentManifest`, `ProjectState`, `OperationsSequence`, protocols, enums. All agents and the API validate against these types.

### `src/eda_platform/agents/`

| Subdirectory | Role | Primary I/O |
|--------------|------|-------------|
| `librarian/` | Ingest datasheets / JSON uploads | PDF or JSON → `ComponentManifest` |
| `architect/` | Template auto-wire | `ProjectState` draft → wired `ProjectState` |
| `logic_checker/` | Electrical / structural rules | `ProjectState` → validation result |
| `operations_refiner/` | Bind steps, timing, fidelity | `OperationsSequence` + schematic → refined sequence |
| `operations_checker/` | Ops vs schematic rules | `OperationsSequence` → validation result |
| `operations_docs/` | Operating procedure markdown | sequence + schematic → text |
| `firmware_engineer/` | Pi 4 pthreads codegen | validated schematic → C tree |

Agents do not call each other’s internals; the API and `orchestration/` coordinate handoffs.

### `src/eda_platform/orchestration/`

Library functions for pipeline stages (refine, validate, merge, approve metadata). Not yet exposed as a single “run pipeline” HTTP endpoint — see roadmap **B4**.

### `hardware_library/`

Long-lived component knowledge. Manifests are shared across projects. Upload API writes here and refreshes the catalog cache.

### `projects/`

Per-project source of truth on disk for API-driven workflows (`demo_robot`, etc.). The **web UI** still keeps most schematic state in memory unless you save via API or files manually — roadmap **A1**.

### `generated/firmware/`

Firmware Engineer output only; never edit by hand. Regenerated from approved schematic (+ optional operations).

### `ui/`

Production schematic editor: catalog, wiring, validation panel, operations panel, datasheet upload, protocol selection. Talks to the API when reachable; falls back to a built-in mock catalog when offline.

### `tests/`

Schema, agent, API, and orchestration tests. Run with `python3 -m pytest` from the repo root.

## Data flow

```
datasheets/ ──► librarian ──► manifests/     (ComponentManifest)
                                    │
         UI / API ──► projects/     │         (ProjectState + operations)
                    schematic         │
                         │            │
                         ▼            │
                  logic_checker ◄─────┘
                         │
              [approve schematic]
                         │
              operations_refiner ──► operations_checker
                         │
              [approve operations]
                         │
                  firmware_engineer ──► generated/firmware/
```
