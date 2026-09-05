# Intelligent EDA & Firmware Code-Generation Platform

Multi-agent swarm for robotics hardware design: datasheet ingestion → schematic layout → validation → threaded firmware generation.

## Architecture

- **Agents:** Hardware Librarian, Systems Architect, Logic Checker, Firmware Engineer
- **Lingua franca:** `ComponentManifest` and `ProjectState` JSON schemas (Pydantic-validated)
- **Docs:** See `docs/architecture/FOLDER_STRUCTURE.md` and `docs/firmware/CONCURRENCY_STRATEGY.md`

## Quick Start

**How-to (at a glance):** [`docs/HOW_TO.md`](docs/HOW_TO.md)

### Full stack (Docker Compose)

```bash
docker compose up --build
# API: http://localhost:8000/health
# UI:  http://localhost:3000
```

### Backend (Python)

```bash
pip install -e ".[dev]"
uvicorn eda_platform.api.main:app --reload --port 8000
python3 -m pytest -v
python3 tests/test_logic_checker.py   # headless Logic Checker integration tests
```

### Frontend (Next.js)

```bash
cd ui && npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev   # http://localhost:3000
npm run test       # net compiler + store unit tests
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| GET | `/api/v1/manifests` | Component catalog |
| POST | `/api/v1/validate` | Run Logic Checker on `ProjectState` |
| POST | `/api/v1/architect/auto-wire` | Template I2C auto-wiring |
| POST | `/api/v1/firmware/generate` | Generate pthreads C firmware for Raspberry Pi 4 |

See `docs/architecture/ENGINEERING_DECISIONS.md` for Phase 4–8 design rationale.

### Firmware output (Phase 9)

After validating and approving a schematic in the UI, click **Generate Firmware**. Output is written to `generated/firmware/<project_id>/`.

On your Raspberry Pi 4:

```bash
cd generated/firmware/<project_id>
make
sudo ./<project_id>_firmware   # requires I2C enabled (raspi-config)
```

## Project Layout

| Directory | Responsibility |
|-----------|----------------|
| `src/eda_platform/schemas/` | Pydantic data validation layer |
| `src/eda_platform/agents/` | Swarm agent implementations |
| `src/eda_platform/orchestration/` | Agent pipeline routing |
| `hardware_library/` | Datasheets and component manifests |
| `projects/` | Per-project schematic state |
| `generated/firmware/` | Output HAL and application code |
| `ui/` | Next.js + React Flow schematic editor |
