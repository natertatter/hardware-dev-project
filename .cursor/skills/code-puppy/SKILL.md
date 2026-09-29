---
name: code-puppy
description: Default project skill for general coding work in this repository when no other skill is selected. Covers repo layout, change discipline, and where to look before editing.
---

# code-puppy

This is the **default skill** for this repository. Follow it when the user has not explicitly selected another skill.

Do not treat this file as a replacement for a skill the user invoked with `/skill-name`, `@skill`, or a Custom Mode.

## Scope

Intelligent EDA and firmware code-generation platform: datasheet ingestion → schematic layout → validation → operations sequences → threaded firmware generation.

Canonical docs (read these instead of guessing):

- `README.md` — architecture, commands, layout
- `docs/HOW_TO.md` — editor, operations, validation, firmware flow
- `docs/architecture/API.md` — HTTP API
- `docs/firmware/CONCURRENCY_STRATEGY.md` — firmware concurrency

## Instructions

- Prefer the smallest change that matches existing patterns in the same directory.
- Do not refactor unrelated code.
- Keep Python (API/agents) and TypeScript (UI) conventions consistent with neighboring files.
- Tests live under `tests/` (pytest) and `ui/` (vitest). Add or update tests when you change behavior that already has coverage.
- Generated firmware under `generated/firmware/` is output; do not hand-edit it as source of truth.
