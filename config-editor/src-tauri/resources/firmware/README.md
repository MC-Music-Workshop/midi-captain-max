# Bundled Firmware

This directory holds the CircuitPython firmware that ships inside the Config Editor
app. The GUI installer (Phase 2+) copies from here onto the connected device.

## How it is populated

- **CI builds** (`.github/workflows/ci.yml`): the `build-zip` job uploads a
  `firmware-zip` artifact; the `build-config-editor-{macos,windows}` jobs download
  and unzip it into this directory before running `npm run tauri build`.
- **Local dev builds**: run `tools/bundle-firmware-for-dev.sh` from the repo root
  before `npm run tauri build` or `npm run tauri dev`.

## Why this README is committed

Only this file is tracked — see `.gitignore`. Committing it guarantees the
directory exists and the Tauri `resources` glob matches at least one entry on a
fresh clone, so the build never fails on an empty directory.

## Contents when populated

Mirrors the `midicaptain-firmware-<version>.zip` artifact: `boot.py`, `code.py`,
`config.json`, `config-mini6.json`, `core/`, `devices/`, `fonts/`, `lib/`,
`firmware.md5`, `VERSION`.
