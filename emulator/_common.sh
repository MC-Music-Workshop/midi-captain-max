#!/bin/bash
# Shared helpers for the Wokwi emulator scripts (setup.sh, test.sh, test-all.sh, run.sh).
# Source this file; it does not run anything on its own.

# Resolve the emulator/ directory regardless of caller's CWD.
EMULATOR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$EMULATOR_DIR/.." && pwd)"

# Device variants with a diagram + test config + scenario.
SUPPORTED_DEVICES="std10 mini6 nano4"

CP_UF2_URL="https://downloads.circuitpython.org/bin/raspberry_pi_pico/en_US/adafruit-circuitpython-raspberry_pi_pico-en_US-7.3.3.uf2"
CP_UF2_FILE="$EMULATOR_DIR/circuitpython.uf2"

# Locate the wokwi-cli binary, honoring an explicit $WOKWI_CLI override and the
# default install location. Exports WOKWI_CLI for callers.
find_wokwi_cli() {
  WOKWI_CLI="${WOKWI_CLI:-wokwi-cli}"
  if ! command -v "$WOKWI_CLI" &> /dev/null; then
    if [ -x "$HOME/.wokwi/bin/wokwi-cli" ]; then
      WOKWI_CLI="$HOME/.wokwi/bin/wokwi-cli"
    else
      echo "Error: wokwi-cli not found. Install: curl -L https://wokwi.com/ci/install.sh | sh" >&2
      return 1
    fi
  fi
  export WOKWI_CLI
}

# Download the CircuitPython runtime UF2 if it isn't already present.
ensure_cp_uf2() {
  if [ ! -f "$CP_UF2_FILE" ]; then
    echo "Downloading CircuitPython 7.3.3 UF2..."
    curl -fL -o "$CP_UF2_FILE" "$CP_UF2_URL"
  fi
}

# Fail early with a helpful message if the CI token is missing.
require_token() {
  if [ -z "$WOKWI_CLI_TOKEN" ]; then
    echo "Error: WOKWI_CLI_TOKEN not set. Get a token at https://wokwi.com/dashboard/ci" >&2
    return 1
  fi
}

# Validate a device name against SUPPORTED_DEVICES.
validate_device() {
  local dev="$1"
  for d in $SUPPORTED_DEVICES; do
    [ "$d" = "$dev" ] && return 0
  done
  echo "Error: unknown device '$dev'. Supported: $SUPPORTED_DEVICES" >&2
  return 1
}
