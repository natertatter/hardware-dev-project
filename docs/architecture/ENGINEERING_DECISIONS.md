# Engineering Decisions (Phases 4–8)

This document records five architectural decisions made when starting Phases 4–8 of the EDA platform. Each choice favors a working vertical slice over premature generality.

## 1. LLM Provider: Abstraction with Anthropic Default (BYOK)

**Decision:** Introduce a provider abstraction layer with Anthropic as the default LLM backend, configured via environment variables (bring-your-own-key).

**Rationale:**
- The Hardware Librarian agent must ingest full PDF datasheets; Anthropic’s long context window is a practical default for that workload.
- A provider interface avoids locking the swarm to one vendor before usage patterns are clear.
- BYOK via env vars keeps secrets out of the repo and matches how teams already manage API keys in CI and local dev.
- Deterministic agents (Logic Checker, template Architect) do not depend on an LLM at all, so the platform remains usable without any key configured.

## 2. Firmware Target: Raspberry Pi 4 (Linux) First

**Decision:** Target Raspberry Pi 4 running Linux as the first generated firmware platform, using pthreads and standard Linux I2C/GPIO interfaces (e.g. `lgpio` / `libgpiod`).

**Rationale:**
- Raspberry Pi 4 is the hardware available for end-to-end testing today — validating on real boards matters more than optimizing for the cheapest MCU dev kit.
- Linux SBCs map naturally to the pthreads row in `docs/firmware/CONCURRENCY_STRATEGY.md`: T0 via `SCHED_FIFO` or isolated threads, T2 I2C via kernel `i2c-dev` with mutexes, T3 on background workers.
- Pi 4 exposes multiple I2C buses and ample RAM/CPU for iterative agent codegen without flash constraints or cross-compilation friction during early development.
- Schematic manifests may still use RP2040 (or other MCUs) as **logical** components in the EDA canvas; the Firmware Engineer maps validated `ProjectState` to Pi 4 pin/bus assignments at codegen time. A dedicated `mcu_rpi4` manifest can be added when schematic and codegen pin maps should align.
- Bare-metal targets (RP2040 + FreeRTOS, STM32, etc.) remain on the roadmap once the Linux pipeline is proven.

## 3. Deployment: Docker Compose for Demos + Dual-Server Local Dev

**Decision:** Provide `docker-compose.yml` for one-command demos while keeping `uvicorn` + `next dev` as the primary local development workflow.

**Rationale:**
- Compose gives reviewers and new contributors a reproducible API + UI stack without documenting every host dependency.
- Split processes in dev preserve fast hot reload (Next.js) and simple Python debugging (breakpoints in FastAPI).
- The API container mounts `hardware_library/` read-only so manifest edits on the host are reflected without rebuilding.
- Production hardening (TLS, auth, orchestration) is intentionally deferred until the agent pipeline is feature-complete.

## 4. Systems Architect v1: Template Auto-Wire Before LLM Layout

**Decision:** Phase 8 ships a deterministic template architect (`template_i2c_layout`) that wires MCU power, GND, and I2C to placed sensors. LLM-driven layout is deferred.

**Rationale:**
- Auto-wire must be testable and idempotent; template rules over known pin names (GPIO4/5, 3V3_OUT, GND) satisfy that.
- The UI needs a working “place components → wire → validate” loop before investing in non-deterministic layout.
- Template output is still valid `ProjectState` JSON, so the Logic Checker and future Firmware Engineer consume the same schema.
- LLM layout can later suggest positions and net names, with the Logic Checker as the safety gate.

## 5. Approval UX: Explicit Two-Step (Approve Schematic → Generate Firmware)

**Decision:** The UI separates **Validate Architecture** from **Approve Schematic**. Firmware generation (Phase 9) will only run on an explicitly approved, validation-passing schematic.

**Rationale:**
- Validation is cheap and repeatable; approval is an intentional human checkpoint before irreversible codegen.
- Editing the canvas after approval clears the approved state, preventing stale firmware from a changed schematic.
- The two-step model maps cleanly to CI: validate on every save, approve/tag for release builds.
- Keeps agent responsibilities clear: Logic Checker validates; the human (or future review agent) approves; Firmware Engineer generates.

---

## Summary Table

| # | Topic | Choice |
|---|--------|--------|
| 1 | LLM provider | Abstraction + Anthropic default, BYOK |
| 2 | Firmware target | Raspberry Pi 4 (Linux, pthreads) |
| 3 | Deployment | Docker Compose + local dual-server dev |
| 4 | Architect v1 | Template I2C auto-wire (deterministic) |
| 5 | Approval UX | Validate, then explicit Approve Schematic |
