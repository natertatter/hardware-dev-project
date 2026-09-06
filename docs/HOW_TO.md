# How to Use the EDA Platform

At-a-glance guide for the schematic editor, validation pipeline, and firmware generation.

## What It Does

Design a hardware schematic in the browser, validate electrical rules automatically, then generate C firmware for **Raspberry Pi 4**.

```
Place components → Auto-wire (optional) → Validate → Approve → Generate firmware
```

---

## Run It

**Fastest (Docker):**

```bash
docker compose up --build
# UI:  http://localhost:3000
# API: http://localhost:8000/health
```

**Local dev (hot reload):**

```bash
pip install -e ".[dev]"
uvicorn eda_platform.api.main:app --reload --port 8000

cd ui && npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

**Windows one-click:** double-click `start-eda-platform.bat` (one window, API + UI). To stop stuck servers: `start-eda-platform.bat stop`

---

## UI Workflow

| Step | Button | What happens |
|------|--------|--------------|
| 1 | Click a component in the **Catalog** | Adds MCU or sensor to the canvas |
| 2 | **Auto-Wire (I2C)** *(optional)* | Wires power, GND, SDA, and SCL between MCU and sensors |
| 3 | **Validate Architecture** | Runs Logic Checker rules; issues appear in the right panel |
| 4 | **Approve Schematic** | Locks in the design for codegen (editing the canvas resets approval) |
| 5 | **Generate Firmware** | Writes C source to `generated/firmware/<project_id>/` |

You can also wire pins manually by dragging connections between node handles instead of using Auto-Wire.

---

## What Gets Checked

The Logic Checker catches common wiring mistakes before firmware is generated:

- Voltage mismatches across a net
- Missing common ground
- Current budget exceeded on a power rail
- Pin used on multiple nets
- Output-to-output conflicts
- UART TX/RX polarity errors
- I2C address collisions

---

## Firmware on Your Pi 4

After step 5 in the UI:

```bash
cd generated/firmware/<project_id>
make
sudo ./<project_id>_firmware   # requires I2C enabled via raspi-config
```

Output includes `main.c`, HAL drivers, pthread tasks, and a `Makefile`.

---

## API (Headless Use)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/manifests` | Component catalog |
| `POST /api/v1/validate` | Validate a `ProjectState` JSON body |
| `POST /api/v1/architect/auto-wire` | Template I2C auto-wiring |
| `POST /api/v1/firmware/generate` | Generate firmware (`approved: true` required) |

Example — validate a project:

```bash
curl -X POST http://localhost:8000/api/v1/validate \
  -H "Content-Type: application/json" \
  -d @projects/demo_robot.example.json
```

---

## Key Folders

| Path | Contents |
|------|----------|
| `hardware_library/manifests/` | Component definitions (add `.json` files here) |
| `projects/` | Example schematic state files |
| `generated/firmware/` | Generated C output (gitignored) |
| `ui/` | Next.js schematic editor |

---

## Adding Components

Drop a new `*.json` manifest into `hardware_library/manifests/`. The API picks it up automatically (no restart needed). Restart the UI catalog if the sidebar doesn't refresh.

See `hardware_library/manifests/*.example.json` for the schema.

---

## Tests

```bash
python3 -m pytest -v          # backend (69 tests)
cd ui && npm run test         # frontend (8 tests)
```
