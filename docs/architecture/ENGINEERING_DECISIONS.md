# Engineering Decisions (Phases 4–8)

This document records five architectural decisions made when starting Phases 4–8 of the EDA platform. Each choice favors a working vertical slice over premature generality.

## 1. LLM Provider: Abstraction with Anthropic Default (BYOK)

**Decision:** Introduce a provider abstraction layer with Anthropic as the default LLM backend, configured via environment variables (bring-your-own-key).

**Rationale:**
- The Hardware Librarian agent must ingest full PDF datasheets; Anthropic’s long context window is a practical default for that workload.
- A provider interface avoids locking the swarm to one vendor before usage patterns are clear.
- BYOK via env vars keeps secrets out of the repo and matches how teams already manage API keys in CI and local dev.
- Deterministic agents (Logic Checker, template Architect) do not depend on an LLM at all, so the platform remains usable without any key configured.

## 2. Firmware Target: RP2040 + FreeRTOS (Pico SDK) First

**Decision:** Target Raspberry Pi Pico (RP2040) with FreeRTOS on the Pico SDK as the first generated firmware platform.

**Rationale:**
- The mock library, manifests, and Logic Checker tests already center on RP2040 + I2C sensors (INA219).
- Pico SDK + FreeRTOS is well documented, cheap to hardware-test, and supports the threaded concurrency model described in `docs/firmware/CONCURRENCY_STRATEGY.md`.
- Shipping one MCU family end-to-end (schematic → validated `ProjectState` → HAL + tasks) proves the pipeline before adding STM32, ESP32, or other targets.
- Pin maps and power budgets in manifests can grow incrementally per MCU rather than blocking on a universal HAL.

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
| 2 | Firmware target | RP2040 + FreeRTOS (Pico SDK) |
| 3 | Deployment | Docker Compose + local dual-server dev |
| 4 | Architect v1 | Template I2C auto-wire (deterministic) |
| 5 | Approval UX | Validate, then explicit Approve Schematic |
