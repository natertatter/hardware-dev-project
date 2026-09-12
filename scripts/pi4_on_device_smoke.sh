#!/usr/bin/env bash
# Run on Raspberry Pi 4 inside a generated firmware directory (Horizon A5).
# Usage:
#   cd generated/firmware/demo_robot && bash /path/to/repo/scripts/pi4_on_device_smoke.sh
#   bash scripts/pi4_on_device_smoke.sh demo_robot /home/pi/eda-firmware/demo_robot
set -euo pipefail

PROJECT_ID="${1:-demo_robot}"
FIRMWARE_DIR="${2:-.}"

if [[ ! -d "$FIRMWARE_DIR" ]]; then
  echo "Firmware directory not found: $FIRMWARE_DIR" >&2
  exit 1
fi

cd "$FIRMWARE_DIR"

echo "==> I2C bus scan (expect sensor address, e.g. 0x40)"
if command -v i2cdetect >/dev/null 2>&1; then
  sudo i2cdetect -y 1 || true
else
  echo "WARN: i2cdetect not installed (sudo apt install i2c-tools)"
fi

echo "==> Build"
make

BINARY="./${PROJECT_ID}_firmware"
if [[ ! -x "$BINARY" ]]; then
  echo "Missing executable: $BINARY" >&2
  exit 1
fi

echo "==> Run (15s cap, sudo for /dev/i2c-1)"
set +e
timeout 15 sudo "$BINARY" 2>&1 | tee /tmp/eda_pi_smoke.log
RUN_STATUS=$?
set -e

if ! grep -q "EDA Platform firmware" /tmp/eda_pi_smoke.log; then
  echo "FAIL: startup banner not found in log" >&2
  exit 1
fi
if ! grep -q "$PROJECT_ID" /tmp/eda_pi_smoke.log; then
  echo "FAIL: project id not found in log" >&2
  exit 1
fi

if [[ $RUN_STATUS -eq 124 ]]; then
  echo "OK — firmware ran until timeout (expected for long-running binary)"
elif [[ $RUN_STATUS -eq 0 ]]; then
  echo "OK — firmware exited cleanly"
else
  echo "WARN — firmware exited with status $RUN_STATUS (check wiring/I2C if errors above)"
fi
