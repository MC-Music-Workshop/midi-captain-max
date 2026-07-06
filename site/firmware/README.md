# Firmware snapshots for the live browser demo

`button.py`, `colors.py`, and `display_model.py` are **verbatim copies** of
`firmware/dev/core/` — do not edit them here. The home page loads them into a MicroPython wasm runtime
so the footswitch demos run the literal firmware logic.

Refresh with `tools/sync-site-firmware.sh` (the Pages deploy workflow runs it
on every deploy, so the live site always matches `main`).
