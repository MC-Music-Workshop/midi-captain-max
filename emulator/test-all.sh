#!/bin/bash
# Run the Wokwi hardware test for every supported device variant in sequence.
# Local convenience wrapper around test.sh; CI runs the variants as a matrix.
#
# Usage: ./emulator/test-all.sh
# Exit codes: 0 = all passed, 1 = one or more failed

set -uo pipefail

EMULATOR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$EMULATOR_DIR/_common.sh"

FAILED=""
for device in $SUPPORTED_DEVICES; do
  echo ""
  if ! "$EMULATOR_DIR/test.sh" "$device"; then
    FAILED="$FAILED $device"
  fi
done

echo ""
echo "=================================="
if [ -n "$FAILED" ]; then
  echo "FAILED devices:$FAILED"
  exit 1
fi
echo "All device hardware tests passed: $SUPPORTED_DEVICES"
