# Horizon C2 and C3 — implementation plan

Written before code changes because the roadmap rows are one line each and do not name fields, provenance rules, or the example-vs-production file contract.

Source rows in [`docs/ROADMAP.md`](../ROADMAP.md):

| ID | Work | Done when |
|----|------|-----------|
| C2 | Provenance in refine | Timing fields flow from manifest into operations provenance |
| C3 | Catalog hygiene | Clear promotion path from `.example.json` to production manifests |

This note is the acceptance contract for the slice. C1 (extract + human commit) stays as already shipped on `cursor/librarian-extract-loop-c77c`. C4 and Horizon D are out of scope.

---

## C2 — Provenance in refine

### Scope in

When `refine_operations` fills a step that has no `timing` yet, copy manifest timing into that step and record where the number came from.

| Manifest field | Step shape | `TimingConstraint.source` | `OperationStep.provenance` |
|----------------|------------|---------------------------|----------------------------|
| `operational_constraints.power_on_delay_ms` on a bound boot / power / enable / wait step | `delay_ms` = that value | `datasheet` | `datasheet` |
| `operational_constraints.conversion_time_ms` on a bound sensor poll/read step, and the value is **≥** the scheduling poll period | `period_ms` = conversion time | `datasheet` | `datasheet` |
| Same conversion time, but the scheduling poll period is **slower** | `period_ms` = scheduling period | `inferred` | `inferred` |
| No matching constraint | existing best-practice constants (`best_practices.py`, scheduling poll) | `best_practice` | `inferred` only when a HAL call was bound; otherwise leave `human` |

`timing.note` names the component and the field (`{component_id} operational_constraints.power_on_delay_ms` or `conversion_time_ms`). When the scheduling plan raises the period, the note also records the datasheet milliseconds and the plan milliseconds.

Rules:

- A step that already has `timing` is left unchanged (human or previously refined numbers are not overwritten).
- Binding a HAL call may set `provenance` to `inferred` only while it is still the default `human`. A datasheet timing fill applied in the same pass then sets `provenance` to `datasheet`, so HAL binding does not hide the datasheet origin.
- The operations sidebar shows the milliseconds plus `timing.source`, and the note is available as the element title.

### Scope out

- `i2c_max_clock_hz` is a bus limit, not a step delay or period. It does not become operations timing.
- No new `TimingConstraint` fields. Provenance stays on the existing `source`, `note`, and step `provenance`.
- No checker rule changes, no firmware emitter changes, no C4 pin schema work.
- Layout-aware / scanned PDF extraction stays unfinished under C1.

### Tests

- Extend `tests/agents/test_manifest_timing.py`: datasheet provenance on the step, scheduling override marked `inferred`, pre-set human timing preserved, missing constraints stay `best_practice`.
- UI: unit-test the timing label helper used by `OperationsPanel`.

---

## C3 — Catalog hygiene

### Current gap

`hardware_library/manifests/` contains only `*.example.json`. `manifest_loader` globs `*.json`, which also matches `*.example.json`, so every example is a live catalog entry. There is no separate production file and no action that promotes one.

`demo_robot` and `GET /api/v1/manifests/mcu_rp2040` depend on `mcu_rp2040` and `sens_ina219` being in that live catalog.

### Data model

| File | Role |
|------|------|
| `{component_id}.example.json` | Template. Not returned by `GET /api/v1/manifests`. Not used when an endpoint omits `manifests`. |
| `{component_id}.json` | Production catalog entry. This is what `load_all_manifests()` reads. |

The `component_id` inside an example file must match the filename stem. A production file wins over an example with the same id; the example is not merged and is not loaded.

### API

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/api/v1/manifests/examples` | Each example: `component_id`, `name`, `type`, `promoted` (production `{component_id}.json` exists). Invalid examples are skipped with a log warning. |
| POST | `/api/v1/manifests/{component_id}/promote` | Validate the example, copy its bytes to `{component_id}.json`, clear the catalog cache. **404** if the example is missing. **409** if the production file already exists. **400** if the JSON is invalid or `component_id` does not match the filename. |

`GET /api/v1/manifests` and `GET /api/v1/manifests/{component_id}` stay production-only. Librarian JSON upload and `POST /librarian/manifests` already write `{component_id}.json`; that remains a second way to create a production file. They do not rewrite `*.example.json`.

In-repo promotion for this slice: copy `mcu_rp2040` and `sens_ina219` to production so `demo_robot` and the existing catalog tests keep working. `sens_bme280`, `mcu_rpi4`, and `mcu_arduino_mega` stay examples until someone promotes them.

### UI

When the parts library is loaded from the API, list unpromoted examples under the catalog with a **Promote** action. Promoting calls the endpoint and reloads the catalog. Offline mock catalog does not show examples.

### Scope out

- No overwrite, no “refresh production from example”, no bulk promote.
- `projects/demo_robot.example.json` is a project fixture, not a component manifest. It is not part of this promotion path.
- No catalog versioning or diff view.

### Tests

- Loader ignores `*.example.json`.
- Promote writes a production file and the catalog then includes it; second promote is 409; missing id is 404.
- `GET /manifests` still contains `mcu_rp2040` and `sens_ina219` and does not contain an unpromoted example id such as `sens_bme280`.
- Vitest covers loading example summaries and the unpromoted filter used by the sidebar.

---

## Docs to update with the implementation

- `docs/ROADMAP.md` — C2 and C3 status after the code matches this note. Mark **Done** only for the contract above. Leave C1 **Partial** and do not start C4.
- `docs/architecture/API.md` — example list, promote, and the refine provenance sentence.
- `docs/HOW_TO.md` — how to promote an example.
- `docs/architecture/FOLDER_STRUCTURE.md` — example vs production filenames.
- `docs/architecture/OPERATIONS_SEQUENCE.md` — refiner timing bullet names manifest fields and provenance.

## Unfinished after this slice

- C1: layout-aware or scanned vendor PDFs.
- C2: `i2c_max_clock_hz` is intentionally not step provenance.
- C3: no overwrite of an existing production manifest from its example.
- C4: `nominal_voltage` on `Pin`, and any other schema work.
