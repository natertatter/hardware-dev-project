# Intelligent EDA & Firmware Code-Generation Platform

Multi-agent swarm for robotics hardware design: datasheet ingestion → schematic layout → validation → operations sequences → threaded firmware generation.

## Architecture

- **Agents:** Hardware Librarian, Systems Architect, Logic Checker, Operations Refiner, Operations Checker, Firmware Engineer
- **Lingua franca:** `ComponentManifest`, `ProjectState`, and `OperationsSequence` JSON schemas (Pydantic-validated)
- **Docs:** [`docs/HOW_TO.md`](docs/HOW_TO.md) · [`docs/ROADMAP.md`](docs/ROADMAP.md) · [`docs/architecture/API.md`](docs/architecture/API.md) · [`docs/architecture/OPERATIONS_SEQUENCE.md`](docs/architecture/OPERATIONS_SEQUENCE.md) · [`docs/firmware/CONCURRENCY_STRATEGY.md`](docs/firmware/CONCURRENCY_STRATEGY.md)

## Quick Start

### Full stack (Docker Compose)

```bash
docker compose up --build
# API: http://localhost:8000/health  (interactive docs: /docs)
# UI:  http://localhost:3000
```

### Backend (Python)

```bash
pip install -e ".[dev]"
uvicorn eda_platform.api.main:app --reload --port 8000
python3 -m pytest -q
```

Optional LLM-assisted operations refine: `pip install -e ".[llm]"` and configure Anthropic credentials per `src/eda_platform/llm/provider.py`.

### Frontend (Next.js)

```bash
cd ui && npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev   # http://localhost:3000
npm run test
```

### API overview

All application routes use the `/api/v1` prefix. See **[`docs/architecture/API.md`](docs/architecture/API.md)** for request bodies, errors, and disk paths.

| Area | Methods | Highlights |
|------|---------|------------|
| Health | `GET /health` | Liveness |
| Catalog | `GET /api/v1/manifests`, `GET .../manifests/{id}` | Hardware library |
| Librarian | `POST /api/v1/librarian/upload` | JSON or PDF → manifest |
| Validation | `POST /api/v1/validate` | Logic Checker |
| Architect | `POST /api/v1/architect/auto-wire` | Template I2C / serial wiring |
| Operations | `GET/PUT .../operations/master`, drafts, refine, validate, merge, approve, generate-docs | See API doc |
| Firmware | `POST /api/v1/firmware/generate` | Pi 4 pthreads C; requires schematic approval; operations approval when sequence provided |

Design rationale for early phases: [`docs/architecture/ENGINEERING_DECISIONS.md`](docs/architecture/ENGINEERING_DECISIONS.md).

### Firmware output

After validating and approving in the UI (and operations when used), **Generate Firmware** writes to `generated/firmware/<project_id>/`.

On Raspberry Pi 4:

```bash
cd generated/firmware/<project_id>
make
sudo ./<project_id>_firmware   # requires I2C enabled (raspi-config)
```

## Project layout

| Directory | Responsibility |
|-----------|----------------|
| `src/eda_platform/schemas/` | Pydantic data validation layer |
| `src/eda_platform/agents/` | Swarm agent implementations |
| `src/eda_platform/orchestration/` | Pipeline stage helpers |
| `hardware_library/` | Datasheets and component manifests |
| `projects/` | Per-project schematic, metadata, operations |
| `generated/firmware/` | Output HAL and application code |
| `ui/` | Next.js + React Flow schematic editor |
