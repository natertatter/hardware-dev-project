# How to Use the EDA Platform

At-a-glance guide for the schematic editor, operations workflow, validation, and firmware generation.

**More detail:** [`architecture/API.md`](architecture/API.md) · **What’s next:** [`ROADMAP.md`](ROADMAP.md)

## What it does

Design a schematic in the browser, capture how the system should **behave**, validate electrical and operations rules, then generate C firmware for **Raspberry Pi 4**.

```
Place parts → (optional) Auto-Wire → Validate → Approve schematic
    → Capture/refine operations → Validate → Approve operations
    → Generate firmware (+ operating docs when operations are active)
```

---

## Run it

**Docker Compose:**

```bash
docker compose up --build
# UI:  http://localhost:3000
# API: http://localhost:8000/health  (OpenAPI: /docs)
```

**Local dev (hot reload):**

```bash
pip install -e ".[dev]"
uvicorn eda_platform.api.main:app --reload --port 8000

cd ui && npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

**Windows:** `start-eda-platform.bat` (waits for API health before opening the UI). Stop stuck servers: `start-eda-platform.bat stop`

**Note:** Compose mounts `hardware_library` into the API container only. Project files under `projects/` and firmware under `generated/` are easiest to persist when running the API on the host — see roadmap **A3**.

---

## UI workflow

### Schematic (left + center)

| Step | Action | What happens |
|------|--------|----------------|
| 1 | **Parts library** or **Datasheet upload** | Add modules to the catalog; PDF upload creates a template manifest (review in `hardware_library/manifests/`) |
| 2 | Click a catalog entry | Places a node on the canvas (optional viewport placement; mock catalog if API is offline) |
| 3 | **Protocol** on multi-bus parts | Switches active pins; invalid edges are removed |
| 4 | Wire pins or **Auto-Wire** | Template connects I2C power/GND/SDA/SCL (and serial links between MCUs when applicable) |
| 5 | **Validate Architecture** | Logic Checker results in the right panel |
| 6 | **Approve** | Locks schematic for codegen; editing the canvas clears approval |

### Operations (right panel)

| Step | Action | What happens |
|------|--------|----------------|
| 1 | Enter narrative / **Save Draft** | Captures light-fidelity intent |
| 2 | **Refine** | Binds steps to nodes, adds timing, may promote fidelity (LLM optional) |
| 3 | **Validate** | Operations Checker rules |
| 4 | **Merge to master** | Promotes refined sequence (API; uses in-memory schematic) |
| 5 | **Approve operations** | Required before **Generate Firmware** when an operations sequence is active |

### Firmware

| Step | Action | What happens |
|------|--------|----------------|
| 1 | **Generate Firmware** | Writes `generated/firmware/<project_id>/` (boot delays from ops when provided) |

The UI currently uses a default in-memory `project_id` (`schematic_project`) and does not save `projects/<id>/schematic.json` automatically — use the API or edit files under `projects/` for disk-backed workflows (see `projects/demo_robot/`).

---

## What gets checked

**Logic Checker** (schematic): voltage mismatches, missing ground, current budget, pin conflicts, UART polarity, I2C address collisions, and related rules.

**Operations Checker** (sequence): node references, dependency cycles, HAL binding hints, timing bounds, boot order warnings, open questions blocking executable fidelity.

---

## Firmware on Raspberry Pi 4

```bash
cd generated/firmware/<project_id>
make
sudo ./<project_id>_firmware   # I2C enabled (raspi-config)
```

Output includes HAL sources, pthread tasks, `Makefile`, and optionally `OPERATING_PROCEDURE.md` / `BRINGUP_CHECKLIST.md`.

---

## API (headless)

Canonical list: [`architecture/API.md`](architecture/API.md).

Quick examples:

```bash
# Validate a fixture
curl -s -X POST http://localhost:8000/api/v1/validate \
  -H "Content-Type: application/json" \
  -d @projects/demo_robot.example.json

# Load operations master for demo_robot
curl -s http://localhost:8000/api/v1/projects/demo_robot/operations/master
```

---

## Key folders

| Path | Contents |
|------|----------|
| `hardware_library/manifests/` | Component definitions |
| `hardware_library/datasheets/` | Uploaded PDFs |
| `projects/` | Per-project schematic, metadata, operations |
| `generated/firmware/` | Generated C (gitignored) |
| `ui/` | Next.js editor |

Add manifests by dropping JSON into `manifests/` or using **Datasheet upload** in the UI / `POST /api/v1/librarian/upload`.

---

## Tests

```bash
python3 -m pytest -q          # backend
cd ui && npm run test           # frontend (vitest)
```

Counts change as tests are added; CI automation is planned (roadmap **A4**).
