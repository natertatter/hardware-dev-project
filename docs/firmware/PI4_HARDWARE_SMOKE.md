# Raspberry Pi 4 hardware smoke (Horizon A5)

Validates the reference path **UI → API → disk → firmware → real Pi 4** without hand-editing JSON. Use this after automated host checks in [`scripts/horizon_a_verify.py`](../../scripts/horizon_a_verify.py).

## What you need

| Item | Notes |
|------|--------|
| Raspberry Pi 4 | Raspberry Pi OS (64-bit recommended), SSH or console |
| I2C sensor | INA219 or BME280 (matches `sens_ina219` / `sens_bme280` manifests) |
| Wiring | 3.3 V, GND, SDA → GPIO2 (pin 3), SCL → GPIO3 (pin 5) |
| Host machine | Repo clone, Python 3.11+, optional Docker for API/UI |

Enable I2C on the Pi: `sudo raspi-config` → Interface Options → I2C → Enable, then reboot.

Confirm the bus sees the sensor (default INA219 address `0x40`):

```bash
sudo i2cdetect -y 1
```

You should see `40` (or your assigned address) in the grid.

## Host: generate firmware from disk (no UI)

From the repository root:

```bash
pip install -e ".[dev]"
python3 scripts/horizon_a_verify.py --write-firmware
```

This loads `projects/demo_robot/`, runs Logic Checker + Operations Checker, generates into `generated/firmware/demo_robot/`, and compiles with `make` when `gcc`/`make` are available.

Copy the output directory to the Pi (example):

```bash
rsync -av generated/firmware/demo_robot/ pi@<pi-host>:~/eda-firmware/demo_robot/
```

## On the Pi: build and run

```bash
cd ~/eda-firmware/demo_robot
make
sudo ./demo_robot_firmware
```

Or use the bundled helper:

```bash
bash scripts/pi4_on_device_smoke.sh demo_robot
```

(run from the copied firmware directory, or pass the path as the second argument — see script header).

### Pass criteria

| Check | Expected |
|-------|----------|
| `make` | Exits 0 |
| Process start | Prints a line containing `EDA Platform firmware` and `demo_robot` |
| Boot delay | Honors operations timing (no immediate crash on I2C open) |
| I2C | No repeated `Failed to read` / bus errors if sensor is wired and addressed correctly |
| Clean exit | Ctrl+C or `timeout 15 sudo ./demo_robot_firmware` ends without segfault |

### Schematic note (MCU on canvas vs Pi target)

Codegen targets **Linux on Raspberry Pi 4**. The checked-in `demo_robot` schematic uses `mcu_rp2040` as a logical MCU node for the editor; generated HAL still assumes the binary runs on the Pi host. For new designs, placing **`mcu_rpi4`** on the canvas better matches deployment (roadmap **D4**). Wiring and I2C pin map follow `hardware_library/platforms/rpi4.json`.

## Full-stack manual smoke (UI)

1. `docker compose up --build` (or local API + UI per [`HOW_TO.md`](../HOW_TO.md)).
2. Open http://localhost:3000 — project **`demo_robot`** should load from disk.
3. **Validate Architecture** → **Approve** → refine/validate operations if used → **Generate Firmware**.
4. Confirm `generated/firmware/demo_robot/` on the host (Compose mounts `generated/`).
5. Complete the on-Pi steps above.

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `i2cdetect` empty | I2C disabled, wrong pins, or sensor not powered |
| Permission denied on `/dev/i2c-1` | Run firmware with `sudo` or add user to `i2c` group |
| API save not on disk in Compose | Ensure API container has `projects/` volume (see `docker-compose.yml`) |
| UI cannot load project | API offline — start API; catalog falls back to mock parts only |
