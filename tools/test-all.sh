#!/bin/bash
# Run every test suite plus the type-freshness check.
#
# Usage: ./tools/test-all.sh
#
# Suites:
#   - pytest (firmware behavior + schema validation + cross-field + drift)
#   - cargo test (Rust config-editor backend)
#   - svelte-check (TypeScript type checking)
#   - generate:types + git diff (catches stale generated types)

set -eo pipefail

# Run from repo root regardless of where the script was invoked from.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Color helpers (no-op when not a TTY)
if [ -t 1 ]; then
  GREEN=$'\033[0;32m'
  RED=$'\033[0;31m'
  BOLD=$'\033[1m'
  RESET=$'\033[0m'
else
  GREEN=""; RED=""; BOLD=""; RESET=""
fi

step() {
  echo
  echo "${BOLD}=== $1 ===${RESET}"
}

step "pytest (Python)"
python3 -m pytest tests/

step "cargo test (Rust)"
(cd config-editor/src-tauri && cargo test)

step "svelte-check (TypeScript)"
(cd config-editor && npm run check)

step "generate:types (schema → TS)"
(cd config-editor && npm run generate:types)

# `git diff --quiet` exits non-zero if there's a diff. Capture and report cleanly.
if ! git diff --quiet config-editor/src/lib/types.generated.ts; then
  echo "${RED}FAIL${RESET}: types.generated.ts is out of date with config.schema.json"
  echo "Commit the regenerated file:"
  echo "  git add config-editor/src/lib/types.generated.ts && git commit"
  exit 1
fi

echo
echo "${GREEN}${BOLD}ALL GREEN${RESET}"
