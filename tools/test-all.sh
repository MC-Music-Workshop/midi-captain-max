#!/bin/bash
# Run every test suite plus the type-freshness and lint checks.
#
# Usage: ./tools/test-all.sh
#
# Suites:
#   - pytest (firmware behavior + schema validation + cross-field + drift)
#   - cargo test (Rust config-editor backend)
#   - svelte-check (TypeScript type checking)
#   - generate:types + git diff (catches stale generated types)
#   - ruff (Python lint)
#   - cargo clippy (Rust lint)

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

step "ruff (Python lint)"
ruff check firmware/ tests/

step "cargo clippy (Rust lint)"
# Warnings-only: the codebase has 2 pre-existing clippy warnings on untouched
# code. Don't promote them to errors here — that's a separate cleanup pass.
(cd config-editor/src-tauri && cargo clippy --lib --no-deps)

echo
echo "${GREEN}${BOLD}ALL GREEN${RESET}"
