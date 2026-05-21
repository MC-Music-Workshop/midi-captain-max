#!/usr/bin/env bash
# Fetch the pinned CircuitPython 7.3.1 .uf2 for raspberry_pi_pico and stage it
# into the Config Editor's Tauri resources so it ships with built apps.
#
# Idempotent: if the file is already present and its SHA256 matches the pin,
# the script is a no-op. Re-downloads only on missing/corrupt file.
#
# Usage (from repo root or anywhere):
#   ./tools/fetch-cp-uf2.sh
#
# Bundled by the GUI to support the "Reflash CircuitPython 7.3.1" button
# (issue #134) — recovery path from CP-version mismatch (#132).
set -euo pipefail

# Pin to upstream Adafruit canonical URL + the SHA256 captured at pin time.
# Bumping the CP target: update both URL and SHA256 together; also update
# MAX_SUPPORTED_CP_MAJOR in installer.rs / deploy.sh / deploy.ps1.
CP_URL="https://downloads.circuitpython.org/bin/raspberry_pi_pico/en_US/adafruit-circuitpython-raspberry_pi_pico-en_US-7.3.1.uf2"
CP_SHA256="1f32b7cd998b3375702a1aca19e2c4487ed589f3460d364716748fe88058c84a"
CP_FILENAME="adafruit-circuitpython-raspberry_pi_pico-en_US-7.3.1.uf2"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST_DIR="$REPO_ROOT/config-editor/src-tauri/resources/circuitpython"
DEST="$DEST_DIR/$CP_FILENAME"

# Cross-platform sha256: macOS ships `shasum`, Linux ships `sha256sum`.
sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        echo "error: neither sha256sum nor shasum found on PATH" >&2
        exit 1
    fi
}

mkdir -p "$DEST_DIR"

# No-op fast path: file already present with the right bytes.
if [[ -f "$DEST" ]]; then
    GOT=$(sha256 "$DEST")
    if [[ "$GOT" == "$CP_SHA256" ]]; then
        echo "✓ CP .uf2 already staged at $DEST (sha256 verified)"
        exit 0
    fi
    echo "! existing $CP_FILENAME has wrong SHA256 (got $GOT, expected $CP_SHA256); re-fetching"
    rm -f "$DEST"
fi

echo "Fetching $CP_FILENAME from $CP_URL..."
# `-fL`: fail on HTTP errors + follow redirects. Adafruit serves these from
# S3 via a CDN that occasionally 30x's.
curl -fL --progress-bar -o "$DEST" "$CP_URL"

GOT=$(sha256 "$DEST")
if [[ "$GOT" != "$CP_SHA256" ]]; then
    echo "error: SHA256 mismatch — got $GOT, expected $CP_SHA256" >&2
    echo "   (refusing to ship a .uf2 we can't verify; deleting the bad file)" >&2
    rm -f "$DEST"
    exit 1
fi

echo "✓ CP .uf2 staged at $DEST (sha256 verified)"
