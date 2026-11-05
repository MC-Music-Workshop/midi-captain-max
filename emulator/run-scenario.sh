#!/bin/bash
# Run one Wokwi scenario against the current firmware/dev source.
#
# A scenario is a directory with:
#   config.json    baked into the simulated CIRCUITPY drive as /config.json
#   scenario.yaml  Wokwi automation steps (press parts, wait for serial lines)
#
# Usage: ./emulator/run-scenario.sh emulator/scenarios/<name> [timeout_ms]
#
# Prerequisites: pip install pyfatfs; wokwi-cli; WOKWI_CLI_TOKEN set.
# Runs in Wokwi's cloud: each run uses CI minutes from your Wokwi plan.
#
# Exit codes: 0 = every step passed; nonzero = failed (42 = --timeout hit; a wait that never
# matches usually hits Wokwi's 5-minute connection limit first and exits 1).
# The serial log is written to <scenario>/serial.log (gitignored).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIO_DIR="$(cd "${1:?usage: run-scenario.sh <scenario-dir> [timeout_ms]}" && pwd)"
TIMEOUT_MS="${2:-120000}"
WOKWI_CLI="${WOKWI_CLI:-wokwi-cli}"

if ! command -v "$WOKWI_CLI" &> /dev/null; then
  if [ -x "$HOME/.wokwi/bin/wokwi-cli" ]; then
    WOKWI_CLI="$HOME/.wokwi/bin/wokwi-cli"
  else
    echo "Error: wokwi-cli not found. Install: curl -L https://wokwi.com/ci/install.sh | sh"
    exit 1
  fi
fi
if [ -z "${WOKWI_CLI_TOKEN:-}" ]; then
  echo "Error: WOKWI_CLI_TOKEN not set. Get one at https://wokwi.com/dashboard/ci"
  exit 1
fi

# Bake this scenario's config into firmware-bundle.uf2 (downloads CP 7.3.3 once).
"$SCRIPT_DIR/setup.sh" --config "$SCENARIO_DIR/config.json" > /dev/null

# `|| status=$?` keeps set -e from exiting before the result is reported.
status=0
"$WOKWI_CLI" \
  --timeout "$TIMEOUT_MS" \
  --scenario "$SCENARIO_DIR/scenario.yaml" \
  --fail-text "Traceback" \
  --serial-log-file "$SCENARIO_DIR/serial.log" \
  --timeout-exit-code 42 \
  "$SCRIPT_DIR" || status=$?

case $status in
  0) echo "PASSED: $(basename "$SCENARIO_DIR")" ;;
  42) echo "TIMEOUT: a step never saw its serial line. See $SCENARIO_DIR/serial.log" ;;
  *) echo "FAILED ($status): see $SCENARIO_DIR/serial.log" ;;
esac
exit $status
