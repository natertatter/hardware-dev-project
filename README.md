# Intelligent EDA & Firmware Code-Generation Platform

Multi-agent swarm for robotics hardware design: datasheet ingestion → schematic layout → validation → threaded firmware generation.

## Architecture

- **Agents:** Hardware Librarian, Systems Architect, Logic Checker, Firmware Engineer
- **Lingua franca:** `ComponentManifest` and `ProjectState` JSON schemas (Pydantic-validated)
- **Docs:** See `docs/architecture/FOLDER_STRUCTURE.md` and `docs/firmware/CONCURRENCY_STRATEGY.md`

## Quick Start

```bash
pip install -e ".[dev]"
pytest
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
| `ui/` | Future web schematic editor |
