#!/bin/bash
# Run the Wokwi hardware test for one device variant.
#
# Builds an all-in-one UF2 from the device's test config (emulator/configs/), runs
# its scenario (emulator/scenarios/<device>.yaml) — which boots the firmware and
# presses simulated footswitches — on Wokwi's simulator, then asserts the emitted
# MIDI by grepping the serial log for every line in scenarios/<device>.expected.
# (Assertions are post-hoc, not scenario wait-serial, because wait-serial can't
# reliably catch press-triggered output — see scenarios/std10.yaml.)
#
# Prerequisites:
#   - pip install pyfatfs
#   - wokwi-cli on PATH (curl -L https://wokwi.com/ci/install.sh | sh)
#   - WOKWI_CLI_TOKEN env var (https://wokwi.com/dashboard/ci)
#
# Usage: ./emulator/test.sh [device]      # device: std10 (default) | mini6 | nano4
#
# Exit codes: 0 = passed, 1 = failed (error detected / assertion timed out)

set -euo pipefail

DEVICE="${1:-std10}"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

validate_device "$DEVICE"
find_wokwi_cli
require_token
ensure_cp_uf2

CONFIG="$EMULATOR_DIR/configs/test-$DEVICE.json"
DIAGRAM="$EMULATOR_DIR/diagram-$DEVICE.json"
SCENARIO="scenarios/$DEVICE.yaml"  # resolved relative to the project dir arg
EXPECTED="$EMULATOR_DIR/scenarios/$DEVICE.expected"
LOG_FILE="$EMULATOR_DIR/test-$DEVICE.log"

for f in "$CONFIG" "$DIAGRAM" "$EMULATOR_DIR/$SCENARIO" "$EXPECTED"; do
  [ -f "$f" ] || { echo "Error: missing $f" >&2; exit 1; }
done

echo "=== Wokwi hardware test: $DEVICE ==="
echo "Building firmware bundle ($DEVICE)..."
python3 "$EMULATOR_DIR/build-uf2.py" --config "$CONFIG" > /dev/null

# wokwi-cli (0.26.1) ignores --diagram-file and only reads <projectdir>/diagram.json,
# so stage the device's diagram as the active diagram.json (gitignored) before running.
cp "$DIAGRAM" "$EMULATOR_DIR/diagram.json"
echo "Running scenario..."

# The scenario runs to completion (boot waits + footswitch presses), then wokwi
# exits. wokwi-cli's --timeout does not reliably bound a stuck boot wait-serial,
# so wrap the call in a hard wall-clock guard (coreutils `timeout`/`gtimeout`)
# when available. Wokwi cloud boot time is variable (10s..40s+), so the guard is
# generous — a genuinely stuck run still fails well within the CI job limit.
TIMEOUT_BIN=""
command -v timeout  &> /dev/null && TIMEOUT_BIN="timeout 200"
command -v gtimeout &> /dev/null && TIMEOUT_BIN="gtimeout 200"

set +e
$TIMEOUT_BIN "$WOKWI_CLI" \
  --timeout 180000 \
  --fail-text "Traceback" \
  --scenario "$SCENARIO" \
  --serial-log-file "$LOG_FILE" \
  "$EMULATOR_DIR"
EXIT_CODE=$?
set -e

echo ""
echo "Serial log: $LOG_FILE"

# A non-zero exit means a boot wait-serial timed out (firmware never booted),
# --fail-text matched a streamed Traceback, or the wall-clock guard fired.
if [ "$EXIT_CODE" -ne 0 ]; then
  echo "FAILED: $DEVICE — emulator run failed (exit $EXIT_CODE): firmware did not" >&2
  echo "        boot, crashed, or timed out. See $LOG_FILE" >&2
  exit 1
fi

# Assert the emitted MIDI: every non-comment line in the .expected file must
# appear in the serial log (literal substring match).
MISSING=0
TOTAL=0
while IFS= read -r line; do
  case "$line" in ''|\#*) continue ;; esac
  TOTAL=$((TOTAL + 1))
  if ! grep -qF -- "$line" "$LOG_FILE"; then
    echo "  MISSING expected output: $line" >&2
    MISSING=$((MISSING + 1))
  fi
done < "$EXPECTED"

# Belt-and-suspenders with --fail-text: fail on any Traceback captured in the log.
if grep -q "Traceback" "$LOG_FILE"; then
  echo "  Python Traceback found in serial output" >&2
  MISSING=$((MISSING + 1))
fi

if [ "$MISSING" -eq 0 ]; then
  echo "PASSED: $DEVICE hardware test ($TOTAL/$TOTAL MIDI assertions matched)"
else
  echo "FAILED: $DEVICE hardware test — $MISSING issue(s); see $LOG_FILE" >&2
  exit 1
fi
