#!/usr/bin/env bash
# Copy the pure firmware modules the home page demo runs (via MicroPython wasm)
# into site/firmware/. Run locally after editing them, or let the Pages deploy
# workflow do it — the deployed site always runs the logic on main.
set -euo pipefail

cd "$(dirname "$0")/.."

cp firmware/dev/core/button.py firmware/dev/core/colors.py \
   firmware/dev/core/display_model.py site/firmware/

echo "Synced firmware/dev/core/{button,colors,display_model}.py -> site/firmware/"
