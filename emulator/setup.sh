#!/bin/bash
# Prepare the emulator: download the CircuitPython runtime UF2 and build an
# all-in-one firmware bundle for one device variant.
#
# test.sh builds its own per-device bundle, so this is mainly for interactive use
# (run.sh) and for poking at the bundle locally.
#
# Usage: ./emulator/setup.sh [device]   # device: std10 (default) | mini6 | nano4
# Prerequisites: pip install pyfatfs

set -euo pipefail

DEVICE="${1:-std10}"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

validate_device "$DEVICE"

echo "=== Wokwi Emulator Setup ($DEVICE) ==="
ensure_cp_uf2

echo "Building firmware bundle..."
python3 "$EMULATOR_DIR/build-uf2.py" --config "$EMULATOR_DIR/configs/test-$DEVICE.json"

echo ""
echo "=== Setup Complete ==="
echo "Next steps:"
echo "  export WOKWI_CLI_TOKEN=your_token   # https://wokwi.com/dashboard/ci"
echo "  ./emulator/test.sh $DEVICE          # automated hardware test"
echo "  ./emulator/run.sh $DEVICE           # interactive"
