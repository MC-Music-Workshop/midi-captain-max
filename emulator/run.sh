#!/bin/bash
# Run a device variant interactively in the Wokwi emulator.
# Serial output streams to your terminal; Ctrl+C to stop.
#
# Usage: ./emulator/run.sh [device]   # device: std10 (default) | mini6 | nano4
# Prerequisites: pip install pyfatfs, wokwi-cli on PATH, WOKWI_CLI_TOKEN set.

set -euo pipefail

DEVICE="${1:-std10}"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

validate_device "$DEVICE"
find_wokwi_cli
require_token
ensure_cp_uf2

echo "Building firmware bundle ($DEVICE)..."
python3 "$EMULATOR_DIR/build-uf2.py" --config "$EMULATOR_DIR/configs/test-$DEVICE.json" > /dev/null

# wokwi-cli (0.26.1) ignores --diagram-file and only reads <projectdir>/diagram.json,
# so stage the device's diagram as the active diagram.json (gitignored) before running.
cp "$EMULATOR_DIR/diagram-$DEVICE.json" "$EMULATOR_DIR/diagram.json"

echo "Starting Wokwi emulator ($DEVICE, interactive). Ctrl+C to stop."
"$WOKWI_CLI" --interactive "$EMULATOR_DIR"
