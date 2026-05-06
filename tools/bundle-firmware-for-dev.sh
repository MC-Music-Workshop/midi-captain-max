#!/usr/bin/env bash
# Stage firmware/dev/ into the Config Editor's Tauri resources directory so local
# `npm run tauri build` / `tauri dev` bundle firmware the same way CI does.
#
# CI uses the mpy-compiled firmware-zip artifact; this dev script ships raw .py
# sources (same as `tools/deploy.sh` pushes to the device) — good enough for
# exercising the installer UI locally.
#
# Usage (from repo root):
#   ./tools/bundle-firmware-for-dev.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/firmware/dev"
DEST="$REPO_ROOT/config-editor/src-tauri/resources/firmware"

if [[ ! -d "$SRC" ]]; then
  echo "error: $SRC not found" >&2
  exit 1
fi

# Wipe everything except the committed README.md placeholder, then repopulate.
mkdir -p "$DEST"
find "$DEST" -mindepth 1 -not -name README.md -not -path "$DEST/README.md/*" -delete

# Same excludes as the CI build-zip job in .github/workflows/ci.yml, plus .DS_Store.
rsync -a \
  --exclude='experiments/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='VERSION.txt' \
  "$SRC"/ "$DEST"/

# Stamp VERSION.txt the same way deploy.sh / ci.yml do.
VERSION="$(git -C "$REPO_ROOT" describe --tags --always 2>/dev/null || echo dev)"
echo "$VERSION" > "$DEST/VERSION.txt"

echo "Staged firmware version $VERSION at:"
echo "  $DEST"
echo "Contents:"
ls -la "$DEST"
