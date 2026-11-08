#!/usr/bin/env bash
# Run the automated bench tests in order and print a markdown results table for
# the release notes. See docs/bench-tests.md.
#
# Tests: din-count.sh, serial-stall.py read, serial-stall.py hold (~10 min total,
#   mostly the hold run). Exits nonzero if any test fails.
# Config: tools/bench/configs/nano4-207-serial-din-test.json on the pedal.
# Setup: one pedal on USB; USB-to-DIN cable OUT -> pedal MIDI IN; nothing else
#   holding the pedal's serial console open.
# Firmware version: --fw-version, else VERSION.txt from a mounted CircuitPython
#   drive, else "unknown" (performance mode hides the drive).
#
# Usage: tools/bench/run.sh [--pedal-port NAME] [--din-port NAME]
#          [--serial /dev/cu.usbmodemXXXX] [--fw-version X.Y.Z]

set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pedal_args=()
din_args=()
serial_args=()
fw_version=""

while [ $# -gt 0 ]; do
  case "$1" in
    --pedal-port) pedal_args=("$1" "$2"); shift 2 ;;
    --din-port) din_args=("$1" "$2"); shift 2 ;;
    --serial) serial_args+=("$1" "$2"); shift 2 ;;
    --fw-version) fw_version="$2"; shift 2 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$fw_version" ]; then
  for f in /Volumes/*/VERSION.txt; do
    # boot_out.txt marks a CircuitPython drive.
    if [ -f "$f" ] && [ -f "$(dirname "$f")/boot_out.txt" ]; then
      fw_version="$(head -1 "$f")"
      break
    fi
  done
fi
fw_version="${fw_version:-unknown}"

rows=()
failed=0
out="$(mktemp -t bench-run)"
trap 'rm -f "$out"' EXIT

# run_test NAME CMD...: streams the test's output, records its last line.
# Each test prints "PASS ..." or "FAIL ..." as its last line; the exit code decides.
run_test() {
  local name=$1 result last
  shift
  echo "### $name" >&2
  "$@" 2>&1 | tee "$out" >&2
  if [ "${PIPESTATUS[0]}" -eq 0 ]; then result=PASS; else result=FAIL; failed=1; fi
  last="$(tail -1 "$out")"
  last="${last#PASS }"
  last="${last#FAIL }"
  # A literal | would split the markdown cell.
  rows+=("| $name | $result | ${last//|/\\|} | $fw_version |")
}

# ${a[@]+"${a[@]}"} expands to nothing for an empty array; plain "${a[@]}"
# errors under set -u on macOS's bash 3.2.
run_test "DIN receive count" "$here/din-count.sh" \
  ${pedal_args[@]+"${pedal_args[@]}"} ${din_args[@]+"${din_args[@]}"}
for mode in read hold; do
  run_test "Serial console stall ($mode)" python3 "$here/serial-stall.py" "$mode" \
    ${pedal_args[@]+"${pedal_args[@]}"} ${serial_args[@]+"${serial_args[@]}"}
done

echo >&2
echo "| Test | Result | Numbers | Firmware |"
echo "|------|--------|---------|----------|"
printf '%s\n' "${rows[@]}"
exit "$failed"
