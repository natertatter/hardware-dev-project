# HTTP API Reference

Base URL (local): `http://localhost:8000`

- **OpenAPI:** `/docs` and `/redoc` when the API is running
- **Version prefix:** `/api/v1` for all routes below except `/health`
- **Manifests:** Unless noted, endpoints accept optional `manifests` in the JSON body; when omitted, the server loads `hardware_library/manifests/*.json` (cached until librarian upload clears cache)

---

## Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check. Returns `{"status":"ok"}`. |

---

## Manifest catalog

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/manifests` | List all `ComponentManifest` entries in the hardware library. |
| GET | `/api/v1/manifests/{component_id}` | Single manifest by `component_id`. **404** if missing. |

---

## Logic Checker

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/v1/validate` | `ValidateRequest`: `project_state`, optional `manifests` | `ValidateResponse`: `valid`, `errors[]` with `rule`, `severity`, `message`, optional `net_id` / `node_id` / `pin_id` |

---

## Systems Architect (template auto-wire)

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/v1/architect/auto-wire` | `AutoWireRequest`: `project_state` (`SchematicDraft` — nodes required, nets may be empty), optional `manifests` | `AutoWireResponse`: full `project_state`, `wires_added` |

**Behavior:** Deterministic template wiring — I2C power/GND/SDA/SCL, protocol-aware pins, and multi-MCU UART/USB serial links when manifests support them. Placement-only drafts get a temporary placeholder net so `ProjectState` validates.

---

## Hardware Librarian

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/v1/librarian/upload` | `multipart/form-data`, field `file` (JSON manifest or PDF) | `UploadManifestResponse`: `manifest`, `saved_path`, `message` |

**Behavior:**

- **JSON:** Validated and saved under `hardware_library/manifests/`.
- **PDF:** Stored under `hardware_library/datasheets/`; a multi-protocol **template** manifest is generated (full datasheet LLM extraction is planned — see [`ROADMAP.md`](../ROADMAP.md)).

Clears the in-memory manifest cache so the next catalog read sees new parts.

---

## Firmware Engineer

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/v1/firmware/generate` | `GenerateFirmwareRequest` | `GenerateFirmwareResponse` |

**`GenerateFirmwareRequest` fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `project_state` | yes | Approved schematic |
| `approved` | yes | Must be `true` (schematic approval gate) |
| `operations` | no | When set, boot delays and operating docs are derived from this sequence |
| `operations_approved` | no | Must be `true` if `operations` is provided |
| `manifests` | no | Server catalog default |

**Errors:** **400** if `approved` is false; **422** on validation or firmware engineer errors.

**Output:** Files under `generated/firmware/<project_id>/` (HAL, `main.c`, `Makefile`, and optionally `OPERATING_PROCEDURE.md`, `BRINGUP_CHECKLIST.md`).

**Target platform:** Raspberry Pi 4 (Linux, pthreads). See [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md).

---

## Projects (schematic + metadata)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/projects` | List project ids that have `schematic.json` on disk. |
| GET | `/api/v1/projects/{project_id}/schematic` | Load `schematic.json` as `SchematicDraft` (`nets` may be empty). **404** if missing. **400** if `project_id` is invalid. |
| PUT | `/api/v1/projects/{project_id}/schematic` | Save `SchematicDraft` as-is (placement-only saves keep `nets: []`). **400** on invalid `project_id`. When nodes/nets change, clears `schematic_approved` and `operations_approved` in metadata; identical saves preserve approvals. |
| GET | `/api/v1/projects/{project_id}/metadata` | Load `metadata.json` or defaults for a new project. |
| PUT | `/api/v1/projects/{project_id}/metadata` | Persist approval flags and fidelity stage. |

---

## Operations sequence

Project artifacts live under `projects/<project_id>/` (`schematic.json`, `metadata.json`, `operations/`). Several routes read or write those paths on disk.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/projects/{project_id}/operations/master` | Load `operations/master.json`. **404** if none. |
| PUT | `/api/v1/projects/{project_id}/operations/master` | Save master; `body.project_id` must match path. |
| POST | `/api/v1/projects/{project_id}/operations/drafts` | Append draft under `operations/drafts/`. Body: `SaveOperationsDraftRequest` (`operations`). |
| POST | `/api/v1/projects/{project_id}/operations/approve` | Set `operations_approved` in metadata after validation. Requires `schematic.json` on disk and passing operations validation. |
| POST | `/api/v1/operations/refine` | `RefineOperationsRequest`: `operations`, `project_state`, optional `manifests`, `persist` (default true). Returns refined sequence, fidelity promotion stats, warnings. |
| POST | `/api/v1/operations/validate` | `ValidateOperationsRequest`: `operations`, `project_state`, optional `manifests`. |
| POST | `/api/v1/operations/merge` | `MergeOperationsRequest`: refined `operations`, optional `project_state` (loaded from disk if omitted), `bump_version`. Validates before promoting to master. **422** if validation fails. |
| POST | `/api/v1/operations/generate-docs` | `GenerateOperatingDocsRequest`: `operations`, `project_state`. Returns markdown strings for operating procedure and bring-up checklist (does not write files; firmware generate also emits docs when operations are passed). |

**LLM:** Refinement can use Anthropic when configured (`pip install -e ".[llm]"` and API key in env); otherwise deterministic fallback.

---

## UI integration notes

The Next.js app uses these endpoints from `ui/src/lib/api.ts`, including project list/load/save and operations workflows. The default reference project is `demo_robot`.

Interactive API docs: start the API and open `http://localhost:8000/docs`.
