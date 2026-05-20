#!/bin/bash
# Validate every firmware/dev/*.py parses under CircuitPython's mpy-cross.
#
# Why: py_compile and pytest run on desktop CPython, which accepts syntax
# CircuitPython 7.x rejects (e.g. adjacent f-string concatenation across
# lines). Files like code.py and boot.py ship as .py and never see the CP
# parser in CI's compile loop, so they need an explicit parse pass.
#
# Skip with: SKIP_MPY_CHECK=1 ./tools/check-circuitpython-parse.sh
# (CI still runs this — local skip is for quick iteration only.)

set -eo pipefail

if [ "${SKIP_MPY_CHECK:-}" = "1" ]; then
  echo "SKIP_MPY_CHECK=1 set, skipping CircuitPython parse check"
  exit 0
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

INSTALL_HINT='Install the Adafruit CircuitPython build (NOT the `mpy-cross` pip
package — that produces MicroPython-format .mpy files incompatible with
CircuitPython, and its parser accepts syntax CircuitPython rejects):

  Linux x86_64:
    curl -sL https://adafruit-circuit-python.s3.amazonaws.com/bin/mpy-cross/linux-amd64/mpy-cross.static-amd64-linux-7.3.3 \
      -o ~/.local/bin/mpy-cross && chmod +x ~/.local/bin/mpy-cross

  macOS (universal, Intel + Apple Silicon):
    curl -sL https://adafruit-circuit-python.s3.amazonaws.com/bin/mpy-cross/macos-11/mpy-cross-macos-11-8.0.4-universal \
      -o ~/.local/bin/mpy-cross && chmod +x ~/.local/bin/mpy-cross
    # Caveat: Adafruit ships no 7.3.3 macOS binary. CP 8.x has a more
    # permissive parser, so this catches MOST CP-only issues but not all.
    # CI runs the linux 7.3.3 build, which is the true gate.

Or skip this check locally with: SKIP_MPY_CHECK=1'

if ! command -v mpy-cross >/dev/null 2>&1; then
  echo "mpy-cross (CircuitPython build) not found on PATH." >&2
  echo >&2
  echo "$INSTALL_HINT" >&2
  exit 1
fi

# Reject MicroPython's pip-installed mpy-cross — its parser differs from
# CircuitPython's and will silently miss CP-incompatible syntax. The Adafruit
# build identifies itself differently; the pip package prints "MicroPython".
MPY_VERSION="$(mpy-cross --version 2>&1 || true)"
if echo "$MPY_VERSION" | grep -qi "MicroPython"; then
  echo "Wrong mpy-cross detected:" >&2
  echo "  $MPY_VERSION" >&2
  echo >&2
  echo "This is the MicroPython pip build. It uses a more permissive parser" >&2
  echo "than CircuitPython and will miss CP-only syntax errors." >&2
  echo >&2
  echo "$INSTALL_HINT" >&2
  exit 1
fi

FAILED=0
TMP_OUT="$(mktemp -t mpy-parse.XXXXXX.mpy)"
trap 'rm -f "$TMP_OUT"' EXIT

while IFS= read -r f; do
  if ! mpy-cross -o "$TMP_OUT" "$f" 2>&1; then
    echo "FAIL: $f"
    FAILED=$((FAILED + 1))
  fi
done < <(find firmware/dev -name "*.py" -not -path "*/experiments/*")

if [ "$FAILED" -gt 0 ]; then
  echo
  echo "$FAILED file(s) failed CircuitPython parse check"
  exit 1
fi

echo "All firmware/dev .py files parse cleanly under CircuitPython mpy-cross"
