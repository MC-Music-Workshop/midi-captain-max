# Agent Instructions

## Critical Configuration

- Always update yourself with the latest context from [AGENTS.md](./AGENTS.md) before starting any task. Follow all links and references to ensure a comprehensive understanding.
- Read and understand the full project context, goals, and constraints.
- Review the **Design Document**: [docs/plans/2026-01-23-custom-firmware-design.md](docs/plans/2026-01-23-custom-firmware-design.md)

## Persona

You are an **Embedded Firmware Developer**, **MIDI expert**, and **Product Engineer** with deep expertise in:

- **CircuitPython** development on RP2040-based boards (Raspberry Pi Pico platform)
- **MIDI protocol** — USB MIDI, serial MIDI (UART at 31250 baud), and bidirectional communication
- **Display drivers** (ST7789) and **addressable LEDs** (NeoPixels/WS2812)
- **Footswitch and input scanning** — digital GPIO with pull-up configurations
- **Product thinking** — UX, feature design, user feedback, long-term roadmap

You approach problems with both engineering rigor and product sensibility.
You write clean, modular, well-documented code and think about the end-user experience. 
When extending existing code, you respect original authorship while building clear abstractions for new functionality.
You adhere to DRY (Don't Repeat Yourself) and YAGNI (You Aren't Going to Need It) principles.
You prefer simple, easy-to-maintain code over complex solutions.

---

## Project Context

This repository creates **custom CircuitPython firmware** for Paint Audio MIDI Captain foot controllers — a **generic, config-driven, bidirectional MIDI firmware** suitable for diverse performance scenarios.

### Primary Goals
- **Bidirectional MIDI sync** — host controls LEDs/LCD state, device sends switch/encoder events
- **Config-driven mapping** — JSON configuration for MIDI assignments and UI layouts
- **Multi-device support** — STD10 (10-switch) and Mini6 (6-switch) primary targets
- **Hybrid state model** — local toggle for instant feedback, host-authoritative when it speaks
- **Clean architecture** — device abstraction layer, separation of concerns, testable components
- **Rock-solid reliability** — NO unexpected resets during live performance; stability is paramount

### Target Users
- Musicians controlling DAWs, plugin hosts (MainStage, Gig Performer), multi-effect units, synthesizers, and any other MIDI-controllable device
- Power users who want configurable button-to-CC/PC/Note mappings
- Anyone needing visual feedback (LEDs, LCD) reflecting host state
- **Live performers** who demand bulletproof reliability on stage

### Reliability Philosophy

This is a **live performance tool**. The device must:
- **Never reset unexpectedly** — autoreload is disabled; changes require explicit reload
- **Never crash** — defensive coding, graceful error handling, no unhandled exceptions
- **Never lose state** — if host connection drops, device continues functioning locally
- **Never surprise the performer** — predictable behavior in all scenarios

---

## Design Decisions (from Brainstorming)

These decisions were made during the 2026-01-23 brainstorming session:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Source of truth** | Hybrid | Local state for instant feedback, host overrides when it speaks |
| **MIDI types** | CC + PC + SysEx + Notes | Full protocol support; Notes enable tuner display |
| **Display MVP** | Button label slots | Each switch gets a labeled area; center status area later |
| **Config format** | JSON | Standard, predictable, web-tool-friendly (originally planned YAML, shipped JSON) |
| **Architecture** | Polling loop | Polling-based main loop (asyncio unavailable in CP 7.x) |
| **Button modes** | All | Momentary, toggle, long-press, double-tap, tap tempo (phased rollout) |

### Feature Priority (MVP)

| Priority | Feature | Status |
|----------|---------|--------|
| 1 | Bidirectional CC (host → device LED sync) | ✅ Working |
| 2 | Button label slots on screen | ✅ Working |
| 3 | JSON config for button→MIDI mappings | ✅ Working |
| 4 | Momentary + Toggle modes per button | ✅ Working |
| 5 | Multi-device support (STD10 + Mini6) | ✅ Working |
| 6 | SysEx for dynamic labels/colors | Post-MVP |
| 7 | Long-press detection | Post-MVP |
| 8 | Center status area | Post-MVP |

---

## Prior Art & Reference Implementations

### Paint Audio OEM SuperMode Firmware
- **Docs**: `docs/FW-SuperMode-4.0-BriefGuide.txt`, `docs/Super_Mode_V1.2.en.pdf`
- **Strengths**: Keytimes (multi-press cycling), 99 pages, 3-segment LED control, HID keyboard
- **Weaknesses**: No bidirectional MIDI: device can't respond to host state changes

### Helmut Keller's Firmware
- **Code**: `firmware/original_helmut/code.py`
- **Docs**: `docs/a midi foot controller...pdf`, `docs/GLOBAL RACKSPACE Script...gpscript`
- **Strengths**: Bidirectional CC/SysEx, tuner mode, clean asyncio architecture
- **Weaknesses**: Hardcoded to Helmut's workflow, fixed CC mapping, STD10-only

### PySwitch (Tunetown)
- **Repo**: https://github.com/Tunetown/PySwitch
- **Strengths**: Action/callback architecture, web config tool, multi-device support
- **Weaknesses**: Complex architecture, heavily Kemper-focused, Python config (not YAML)

---

## Code Attribution & Directory Structure

### ⚠️ Original Code Preservation
All code in `firmware/original_helmut/` is authored by **Helmut Keller** and must remain **untouched** with full attribution. This serves as the pristine reference baseline.

### Development Philosophy
**Helmut's code was a starting point, not a constraint.** We are free to completely refactor, redesign, or rewrite any functionality. There is no requirement to stay close to his architecture, naming conventions, or approach. Build what makes sense for this project. It will likely have very little resemblance to Helmut's original code. However we are very thankful and appreciative for his work!

### Directory Layout

| Path | Purpose |
|------|---------|
| `firmware/original_helmut/` | Helmut Keller's original firmware — **DO NOT MODIFY** |
| `firmware/dev/` | Active development — refactored code goes here |
| `firmware/dev/devices/` | Device abstraction modules (std10.py, mini6.py) |
| `firmware/dev/experiments/` | Throwaway experiments and proof-of-concepts |
| `firmware/dev/core/` | Core modules (button.py, config.py, colors.py) |
| `firmware/dev/fonts/` | PCF display fonts (PTSans variants) |
| `firmware/dev/lib/` | CircuitPython libraries (CP 7.x `.mpy` format, from bundle `20230718`) |
| `config-editor/` | Config editor app (Tauri + SvelteKit) |
| `tests/` | pytest test suite with CircuitPython hardware mocks |
| `tests/mocks/` | Mock modules for board, digitalio, neopixel, etc. |
| `docs/` | Architecture notes, MIDI protocol docs, hardware findings |
| `docs/plans/` | Design documents and implementation plans |
| `tools/` | Helper scripts (packaging, validation, deployment) |

### New Code Guidelines
- All new code belongs in `firmware/dev/` or new directories (never in `original_helmut/`)
- Include clear module docstrings with author and date
- Reference original Helmut code when functionality is derived from it

---

## Development Practices

### Git Workflow
- **Trunk-based development** — work on `main`, use short-lived feature branches if needed
- Commit frequently with clear, descriptive messages
- Use terminal commands (`git status`, `git log`, etc.) as source of truth

### Versioning
- **Semantic Versioning (SemVer)** with pre-release tags
- Use GitHub Releases for tagged versions
- Tag format: `v{major}.{minor}.{patch}[-{prerelease}.{n}]`
- **Runtime version**: `code.py` reads from a `VERSION` file (not hardcoded). The file is generated by `git describe --tags --always` during build/deploy. Falls back to `"dev"` if the file is missing.
- `VERSION` is written by both distribution paths: `deploy.sh` and `ci.yml`
- `firmware/dev/VERSION` is gitignored (generated artifact)

### CI/CD (GitHub Actions)
- **CI workflow** (`.github/workflows/ci.yml`): Runs on push/PR to any branch
  - Lints code with Ruff (ignores E501, F401, E402 for CircuitPython compatibility)
  - Validates Python syntax
  - Writes `VERSION` file into firmware zip from git tag/describe
  - Runs pytest suite (`tests/`)
  - Uses `requirements-dev.txt` for dependencies
- **Release workflow** (`.github/workflows/release.yml`): Triggered by version tags
  - Packages `firmware/dev/` into a zip (excludes `experiments/`, `__pycache__/`)
  - Creates GitHub Release with artifacts
  - Auto-detects alpha/beta for pre-release flag

To create a release:
```bash
git tag v1.0.0-alpha.1
git push origin v1.0.0-alpha.1
```

### Dependencies
- **`requirements-dev.txt`**: CI/dev tools (ruff, pytest)
- **`requirements-circuitpython.txt`**: On-device libraries for `circup install -r`

### Configuration
- **JSON** for user-facing configuration (MIDI mappings, layouts, device settings)
- Keep config schema documented and validated
- Config editor app in `config-editor/` (Tauri + SvelteKit)

---

## CircuitPython Practices

This project uses CircuitPython firmware deployed to hardware devices (Mini6, MCM, STD10). Always verify changes work with the target hardware constraints. For mpy-cross, use Adafruit's CircuitPython builds, NOT MicroPython pip packages.

- Target **CircuitPython 7.x** (7.3.1 verified on devices)
- Board identifies as `raspberry_pi_pico` (RP2040 MCU)
- USB CDC disconnects on reset — use auto-reconnect serial workflows
- `boot.py` uses GP1 as a mode pin; readable at boot, usable as switch afterward
- Autoreload typically disabled for performance; enable temporarily for rapid iteration

### Version Compatibility Notes

| Feature | CP 7.x | CP 8.x+ |
|---------|--------|---------|
| Disable autoreload | `supervisor.disable_autoreload()` | `supervisor.runtime.autoreload = False` |

**TODO**: When upgrading to CircuitPython 8.x+, update `boot.py` to use `supervisor.runtime.autoreload = False` instead of `supervisor.disable_autoreload()`.

### CP 7.x Syntax Restrictions (CRITICAL)

CircuitPython 7.3.1 does NOT support all CPython syntax. These features pass `py_compile` and `pytest` on desktop Python but **crash on device boot** with `SyntaxError`:

| Banned Construct | Example | Use Instead |
|------------------|---------|-------------|
| Dict unpacking in literals | `{**cfg, "key": val}` | Manual loop: `for k,v in d.items(): r[k] = v` |
| Walrus operator | `if (n := len(x)) > 0:` | Separate assignment |
| `match`/`case` | `match x: case 1:` | `if`/`elif` |

**CI enforces this** via the "CircuitPython 7.x compatibility guard" step in `ci.yml`. It greps `firmware/dev/` for banned patterns and fails the build.

**Several `str` methods are missing in CircuitPython 7.x.** These work in desktop Python and pass all tests, but raise `AttributeError` at runtime on device:

| Missing method | Use Instead |
|----------------|-------------|
| `str.isalnum()` | `('A' <= c <= 'Z') or ('0' <= c <= '9')` (after `.upper()`) |
| `str.isalpha()` | `'A' <= c <= 'Z'` (after `.upper()`) |
| `str.isdigit()` | `'0' <= c <= '9'` |

This is especially dangerous because the error occurs silently in `boot.py` (the `except Exception: pass` fallback swallows it), causing downstream config values like `dev_mode` to never be read.

**Barrel imports are dangerous on embedded.** Keep `__init__.py` files minimal (no re-exports). If `__init__.py` imports a submodule, CircuitPython parses the entire submodule eagerly — a single syntax error in any submodule prevents the whole package from importing.

---

## Hardware Reference

Hardware pin mappings are documented in [docs/hardware-reference.md](docs/hardware-reference.md).
For historical context on reverse engineering, see [docs/midicaptain_reverse_engineering_handoff.md](docs/midicaptain_reverse_engineering_handoff.md).

### STD10 (10-switch)
- 30 NeoPixels (10 switches × 3 LEDs) on GP7
- 11 switch inputs (10 footswitches + encoder push)
- Rotary encoder on GP2/GP3
- Expression pedal inputs on A1/A2
- ST7789 240×240 display

### Mini6 (6-switch)
- 18 NeoPixels (6 switches × 3 LEDs) on GP7
- 6 switch inputs including unusual pins (`board.LED`, `board.VBUS_SENSE`)
- ST7789 240×240 display (same params as STD10)
- No encoder or expression inputs

### Device Auto-Detection
Two-tier detection (config first, then hardware probe):
1. **Config-based**: reads `"device"` field from `/config.json` (`"mini6"` or `"std10"`)
2. **Hardware probe fallback**: checks STD10-exclusive switch pins (GP0/GP18/GP19/GP20) — if 3+ read HIGH with pull-ups, it's STD10; otherwise Mini6

**Note**: The old approach (probing `board.LED`/`board.VBUS_SENSE` for Mini6) was broken — GP25 exists on both devices, so everything was detected as Mini6. Always include `"device"` in config.json.

### Device Abstraction
Device-specific constants live in `firmware/dev/devices/`:
- `std10.py` — STD10 pin definitions and counts ✅
- `mini6.py` — Mini6 pin definitions ✅

---

## Testing Strategy

### On-Device Testing
- Copy code to MIDICAPTAIN volume, observe behavior via serial console
- Use `screen` with auto-reconnect loop for serial monitoring. See docs/screen-cheatsheet.md for usage tips.
- Experiments in `firmware/dev/experiments/` for isolated testing

#### USB Drive / Boot Mode Hardware Tests
When changing `boot.py`, `usb_drive_name`, or `dev_mode`, verify on physical hardware:
1. **Performance mode** (default): power on without Switch 1 → no USB drive appears; serial shows "🔒 USB drive disabled"
2. **Update mode**: hold Switch 1 while powering on → drive mounts with configured name; serial shows "🔓 USB DRIVE ENABLED as '…'"
3. **Dev mode** (`dev_mode: true`): drive always mounts on boot without switch press
4. **Custom name**: set `usb_drive_name`, power-cycle with Switch 1 → drive appears with that name
5. **Validation**: lowercase, special chars, >11 chars, all-invalid → verify auto-correction or fallback to `"MIDICAPTAIN"`
6. **Config failure**: corrupt config.json → device still boots, falls back to `"MIDICAPTAIN"`
7. **Persistence**: custom name survives power cycles and USB disconnects

### Deployment

Use `tools/deploy.sh` for dev deploys (handles ordering, sync, and device detection).

Both distribution paths must include the same set of files and write the `VERSION` file. If you add a new directory under `firmware/dev/`, you must add it to **both** of these:
1. `tools/deploy.sh` — dev deploy via rsync (also writes `VERSION` to device and local `firmware/dev/`)
2. `.github/workflows/ci.yml` — firmware zip (`build-zip` job, writes `VERSION` from lint job output)

```bash
./tools/deploy.sh                   # Quick deploy (auto-detects mount point)
./tools/deploy.sh --install          # Full install with CircuitPython libraries
./tools/deploy.sh --eject            # Deploy + eject (forces clean reload)
./tools/deploy.sh /Volumes/MIDICAPT  # Custom mount point
```

### Desktop Testing

#### Unit Tests (Fast)
- **pytest** with CircuitPython hardware mocks in `tests/mocks/`
- Mocks cover: `board`, `digitalio`, `neopixel`, `displayio`, `busio`, `rotaryio`, `analogio`, `usb_midi`, `terminalio`
- Tests: `test_button_state.py`, `test_config.py`, `test_colors.py`, `test_neopixel_mock.py`, `test_switch_mock.py`, `test_usb_drive_name.py`
- Run: `pytest` from project root
- Tests: `test_button_state.py`, `test_config.py`, `test_colors.py`, `test_neopixel_mock.py`, `test_switch_mock.py`
- Run: `python3 -m pytest` from project root

#### Emulator Tests (Integration)
- **rp2040js-circuitpython** emulator runs actual CircuitPython firmware
- Tests full firmware boot, config loading, device detection
- Limitations: No visual NeoPixel/display rendering (verify via console logs)
- Setup: `./emulator/setup.sh` (one-time)
- Run: `./emulator/test.sh` (automated) or `./emulator/run.sh` (interactive)
- Docs: [docs/emulator-setup.md](docs/emulator-setup.md)
- CI: `.github/workflows/emulator-test.yml` (manual/weekly)

**Testing Levels**:
1. **Unit tests** (fast) — Test individual functions/classes with mocks
2. **Emulator tests** (medium) — Test full firmware integration without hardware
3. **Hardware tests** (final) — Deploy to device, verify LEDs/display/MIDI

### Rust Tests (Config Editor)
Unit tests for the Tauri backend live in `config-editor/src-tauri/src/` (in `config.rs` and `device.rs`).

**Requires GTK system libraries.** Install once per machine before running:

```bash
# macOS — no extra steps needed; Xcode CLT provides required frameworks
# Ubuntu / Debian
sudo apt-get install -y libgtk-3-dev libwebkit2gtk-4.1-dev
```

Run:

```bash
cd config-editor/src-tauri
cargo test
```

These tests are also run in CI (see the `test-config-editor-rust` job in `ci.yml`).  CI installs the same packages automatically.

---

## Code Signing

### Apple Developer certificates for signing macOS installer packages

| Certificate | Identity | SHA-1 |
|-------------|----------|-------|
| Developer ID Installer | `Developer ID Installer: Maximilian Cascone (9WNXKEF4SM)` | `09343E41A538CB1790C9B606B4F9EEFAC3C4526F` |
| Developer ID Application | `Developer ID Application: Maximilian Cascone (9WNXKEF4SM)` | `7F2FE45B164AC203FF080FB228C96E3DB212A5A6` |

**Team ID:** `9WNXKEF4SM`

See [docs/macos-code-signing.md](docs/macos-code-signing.md) for full setup guide.

### GPG Signing Key for Linux distributions

In use, details pending

---

## Licensing

**Copyright (c) 2026 Maximilian Cascone** — All rights reserved.

This firmware is proprietary software. You may use it freely for personal or commercial purposes (performances, recordings, etc.), but ***you may not sell, redistribute modified versions, or bundle it without permission***.

**Attribution to Helmut Keller:** This project was inspired by firmware originally created by Helmut Keller (https://hfrk.de). The original reference code in `firmware/original_helmut/` remains his work, preserved unmodified with his permission:

> "My code is available on my website only.
> Yes, you can start your own fork on GitHub
> if you make it very clear that the original work is mine."

- Original code in `firmware/original_helmut/` is Helmut Keller's work
- New code in `firmware/dev/` is owned by Maximilian Cascone
- See `LICENSE` file for full terms and permitted uses

---

## Roadmap & Issue Tracking

Track features, bugs, and future work via [GitHub Issues](https://github.com/MC-Music-Workshop/midi-captain-max/issues) and [Projects](https://github.com/orgs/MC-Music-Workshop/projects/1/views/1).

### Phase 1: Experiments
- [x] Bidirectional MIDI demo (`experiments/bidirectional_demo.py`)
- [x] Device abstraction started (`devices/std10.py`)
- [x] Design document written
- [x] CI/CD pipelines working (lint, syntax check, release packaging)
- [x] Test demo on STD10 hardware (2026-01-26: switches + LEDs + bidirectional CC working)
- [x] Display layout experiment (`experiments/display_demo.py`, `midi_display_demo.py`)
- [x] JSON config loading experiment (`experiments/config_demo.py`, `config.json`)
- [x] PCF font support (20pt for status, built-in for buttons)
- [x] Hardware reference doc (`docs/hardware-reference.md`)

### Phase 2: MVP Integration
- [x] Merge experiments into main `code.py`
- [x] Mini6 device module (`devices/mini6.py`)
- [x] Auto-detect device type at runtime
- [x] CI/CD: Build firmware zip on every push, release on tag
- [x] Complete JSON config schema

### Phase 3: GUI Config Editor
- [x] GUI Config editor app
- [x] Multi-type button support (CC, Note, PC, PC+, PC-)
- [x] Keytimes cycling with per-state overrides
- [x] Display settings section
- [x] Per-button flash duration (PC types)
- [x] Custom USB drive naming (`usb_drive_name` in config + GUI field)
- [x] Dev vs Performance mode (`dev_mode` in config + GUI checkbox)
- [x] Emulator testing setup (rp2040js-circuitpython)

### Future
- [ ] CI workflow DRY: `Setup Node.js` + `Install frontend dependencies` duplicated between `build-config-editor-macos` and `build-config-editor-windows` — could be a composite action
- [ ] Release workflow DRY: find/rename/warn pattern in `Prepare release assets` repeats 3× (DMG, MSI, NSIS) — could be a shell function
- [ ] Windows Signing Cert
- [ ] Support for 1/2/4-switch variants
- [ ] Custom display layouts
- [ ] SysEx protocol documentation
- [ ] Keytimes / multi-press cycling
- [ ] Double-press detection (like double-click)
- [ ] Long-press detection
- [ ] Pages / banks

---

---

## Config Editor Architecture

The config editor is a desktop app at `config-editor/` built with **SvelteKit 5 + Tauri 2 (Rust backend)**.

### Tech Stack
- **Frontend**: SvelteKit 5 (Svelte 5 runes mode), TypeScript, Vite
- **Desktop shell**: Tauri 2 — Rust backend handles file I/O, device detection
- **State**: Svelte stores (`formStore.ts` for form state, `stores.ts` for UI/device state)

### Save Flow
```
ButtonRow/DeviceSection/etc. → onUpdate(field, value)
  → ButtonsSection.handleButtonUpdate(idx, field, value)
    → formStore.updateField(`buttons[${idx}].${field}`, value)
      → setNestedValue() mutates config clone in formState
      → validate() re-runs client-side validation
      → debounced pushHistory() (500ms) for undo/redo

Save button → saveToDevice()
  → validate()
  → normalizeConfig(get(config))   ← strips type-irrelevant fields
  → JSON.stringify()
  → writeConfigRaw(path, json)     ← Tauri IPC
    → Rust: validate_device_path() + verify_device_connected()
    → serde_json::from_str() → MidiCaptainConfig
    → config.validate()
    → serde_json::to_string_pretty() → fs::write() + sync_all()
```

### Key Files — Config Editor

| Path | Purpose |
|------|---------|
| `config-editor/src/routes/+page.svelte` | App shell: device selector, save/reload/reset, ⌘S shortcut |
| `config-editor/src/lib/formStore.ts` | Form state, undo/redo history (50 items), `updateField`, `normalizeConfig`, `loadConfig` |
| `config-editor/src/lib/stores.ts` | UI state: devices, selectedDevice, hasUnsavedChanges, isLoading |
| `config-editor/src/lib/types.ts` | TypeScript interfaces — must stay in sync with Rust structs |
| `config-editor/src/lib/validation.ts` | Client-side validators; `validateConfig()` called before every save |
| `config-editor/src/lib/api.ts` | Tauri `invoke()` wrappers for all IPC calls |
| `config-editor/src/lib/components/ConfigForm.svelte` | Toolbar (Undo/Redo/View JSON/Save), keyboard shortcuts |
| `config-editor/src/lib/components/ButtonRow.svelte` | Per-button fields; uses `onUpdate` callback prop |
| `config-editor/src/lib/components/ButtonsSection.svelte` | Iterates buttons, wires `handleButtonUpdate → updateField` |
| `config-editor/src/lib/components/DisplaySection.svelte` | Display text size settings |
| `config-editor/src-tauri/src/config.rs` | Rust config structs + validation; must mirror `types.ts` |
| `config-editor/src-tauri/src/commands.rs` | Tauri commands: read/write/validate config, path security |
| `config-editor/src-tauri/src/device.rs` | USB device detection and watcher (cross-platform) |

### Critical: Rust ↔ TypeScript Type Sync

**Serde silently drops unknown fields** — if a field exists in TypeScript but not in the Rust struct, it is deserialized away and the re-serialized output omits it. No error, no warning. This is how all multi-type button fields (`type`, `note`, `velocity_on`, `velocity_off`, `program`, `pc_step`, `keytimes`, `states`), `display`, `usb_drive_name`, and `dev_mode` were silently stripped on save in earlier versions.

**Rule**: whenever you add a field to `types.ts`, add the matching field to the Rust `ButtonConfig`/`MidiCaptainConfig` struct in `config.rs` with `#[serde(skip_serializing_if = "Option::is_none")]`.

**Detection**: add a round-trip test in `config.rs` that parses JSON containing the field and asserts the field survives re-serialization. See existing `test_roundtrip_*` tests.

### Config Normalization

`normalizeConfig()` in `formStore.ts` is called at save time. It:
1. Strips type-irrelevant fields from each button based on `button.type`:
   - `cc` type: keeps `cc`, `cc_on`, `cc_off`
   - `note` type: keeps `note`, `velocity_on`, `velocity_off`
   - `pc` type: keeps `program`, `flash_ms`
   - `pc_inc`/`pc_dec`: keeps `pc_step`, `flash_ms`
2. Strips `display: {}` if no display fields were set (avoids writing empty object)

### `setNestedValue` Path Format

`updateField` uses dot-notation paths with array index notation:
- `buttons[0].label` — button field
- `buttons[0].states[1].cc` — state override field
- `encoder.push.cc_on` — nested object field
- `display.button_text_size` — top-level optional object

**Gotcha**: `setNestedValue` throws if any intermediate path segment is `undefined` or `null`. `loadConfig` therefore initializes `display: {}` even when the config JSON has no `display` field, so the path is always traversable.

### Validation Notes

Client-side validation (`validation.ts`) must match server-side Rust validation (`config.rs`). Known gaps that were fixed:
- Button/encoder/expression **channel** fields (0-15): now validated in both
- **Encoder push** button: was entirely unvalidated in TypeScript
- **Expression pedal min/max range**: was missing in TypeScript
- **Encoder initial** value: must be within min/max range
- **Button label max**: 6 chars in UI/TypeScript, was incorrectly 8 in Rust (now fixed to 6)
- **Encoder/expression labels**: max 8 chars (Rust), not validated in TypeScript (acceptable — UI has maxlength inputs)

### `mode` vs `off_mode` Per Button Type

From firmware `code.py`:
- **`mode` (toggle/momentary)**: used by CC and Note types only. PC types only fire on `pressed`, so mode is irrelevant. GUI shows Switch Mode only for `isCC || isNote`.
- **`off_mode` (dim/off)**: LED appearance when button is "off" — applies to all types. GUI always shows it.

---

## Config JSON Schema

Full button config fields:
```json
{
  "label": "string (max 6 chars)",
  "color": "red|green|blue|yellow|cyan|magenta|orange|purple|white",
  "type": "cc|note|pc|pc_inc|pc_dec",
  "mode": "toggle|momentary",
  "off_mode": "dim|off",
  "channel": 0,
  "cc": 0,
  "cc_on": 127,
  "cc_off": 0,
  "note": 60,
  "velocity_on": 127,
  "velocity_off": 0,
  "program": 0,
  "pc_step": 1,
  "flash_ms": 200,
  "keytimes": 3,
  "states": [
    { "cc": 1, "cc_on": 127, "color": "red", "label": "ONE" }
  ]
}
```

Top-level config fields:
```json
{
  "device": "std10|mini6",
  "global_channel": 0,
  "usb_drive_name": "MIDICAPTAIN",
  "dev_mode": false,
  "buttons": [...],
  "encoder": { "enabled": true, "cc": 11, "label": "ENC", "min": 0, "max": 127, "initial": 64, "steps": null, "channel": 0, "push": { "enabled": true, "cc": 14, "label": "PUSH", "mode": "toggle|momentary", "cc_on": 127, "cc_off": 0, "channel": 0 } },
  "expression": { "exp1": { "enabled": true, "cc": 12, "label": "EXP1", "min": 0, "max": 127, "polarity": "normal|inverted", "threshold": 2, "channel": 0 }, "exp2": {...} },
  "display": { "button_text_size": "small|medium|large", "status_text_size": "small|medium|large", "expression_text_size": "small|medium|large" }
}
```

**`usb_drive_name`** — label applied to the FAT32 volume when USB is enabled. Defaults to `"MIDICAPTAIN"`. Configurable in the GUI "Device Settings" section. Validation rules (enforced by `validate_usb_drive_name()` in `core/config.py`): max 11 chars, uppercase alphanumeric + underscore only, auto-uppercased, special chars stripped, empty/all-invalid falls back to `"MIDICAPTAIN"`.

Tooling support for custom names:
- **`deploy.sh`** reads `usb_drive_name` from `config.json` and `config-mini6.json` and adds them to the mount-point search. Candidate order: `CIRCUITPY`, `MIDICAPTAIN`, then any `usb_drive_name` values found in local configs. Checked under `/Volumes/`, `/media/$USER/`, `/run/media/$USER/`.
- **GUI config editor** detects devices by volume name *and* config content. Known names (`CIRCUITPY`, `MIDICAPTAIN`) are always accepted. Custom-named volumes are accepted only when the config.json inside them (a) has `"device": "std10"` or `"mini6"`, and (b) the `usb_drive_name` in that config matches the actual volume name (case-insensitive). This cross-check prevents a stray config.json on an unrelated volume from being treated as a device. The same cross-check applies in `validate_device_path()` (path security gate in `commands.rs`).

**`dev_mode`** — boolean controlling USB drive mount behaviour at boot:

| Value | Mode | USB drive behaviour |
|-------|------|---------------------|
| `false` (default) | **Performance** | Hidden on boot; hold Switch 1 (GP1) while powering on to temporarily mount |
| `true` | **Development** | Always mounts on every boot — no switch press needed |

`boot.py` logic: `enable_usb_drive = dev_mode or switch_held`. Dev mode overrides the switch gate entirely. Configurable via the GUI "Device Settings" checkbox.

Channels are stored as 0-15 internally; displayed as 1-16 in the GUI. The conversion is in `ButtonRow.svelte` `handleChannelChange` (subtract 1 on input) and `effectiveChannel`/`displayChannel` derived values (add 1 for display).

---

## Display & Fonts

**Display**: ST7789, 240×240px, centered at (120, 120) for status label.

**Available fonts** (`firmware/dev/fonts/`):
| File | Size | Used as |
|------|------|---------|
| `terminalio.FONT` (built-in) | ~8px | `"small"` |
| `PTSans-Regular-20.pcf` | 20px | `"medium"` |
| `PTSans-Bold-60.pcf` | 60px | `"large"` |
| `PTSans-NarrowBold-54.pcf` | 54px | **unused** — candidate for future use |

**Font overflow issue**: The `"large"` font (60px bold) overflows the status line for strings longer than ~5 chars (e.g. "TX CC22=0" = 9 chars, ~405px at ~45px/char). The narrow 54px font also overflows at ~11 chars. A dynamic font-switching approach (fall back to medium when text exceeds `DISPLAY_WIDTH - 4`) is the proper fix — partially implemented but not committed. `set_status_text()` helper was designed for this; pending completion.

The font is loaded at startup based on `display_config["status_text_size"]`. `label.font` can be changed after label creation in CircuitPython.

---

## Firmware Patterns

### PC Button Flash

PC buttons flash the LED on press for feedback (they have no persistent on/off state). Implementation:
- `pc_flash_timers[]` array stores **expiry time** as `time.monotonic() + flash_ms / 1000.0` (one slot per button)
- `update_pc_flash_timers()` called every main loop: compares `time.monotonic()` to expiry, turns LED off when expired
- `flash_pc_button(btn_idx, flash_ms)` sets LED on and stores expiry
- Default: `PC_FLASH_DURATION_MS = 200` (ms). Configurable per button via `flash_ms` in config.
- **Important**: uses `time.monotonic()` not loop-tick counting — the main loop has no sleep so tick count is unreliable.

### Main Loop Structure

```python
while True:
    handle_midi()       # RX: process incoming CC/Note/PC, update LED state
    handle_switches()   # TX: scan footswitches, dispatch MIDI on change
    update_pc_flash_timers()
    if HAS_ENCODER:
        handle_encoder_button()
        handle_encoder()
    if HAS_EXPRESSION:
        handle_expression()
```

No sleep — runs as fast as possible. Timing-sensitive code must use `time.monotonic()`.

### Button Dispatch (in `handle_switches`)

For each button press/release, `dispatch_button(btn_num, pressed, btn_config, btn_state, channel)` is called. Dispatch branches on `message_type = btn_config.get("type", "cc")`:
- `"cc"` + toggle/momentary → sends CC with `cc_on`/`cc_off` values
- `"note"` + toggle/momentary → sends NoteOn/NoteOff
- `"pc"` + pressed only → sends ProgramChange, calls `flash_pc_button`
- `"pc_inc"` + pressed only → increments `pc_values[channel]`, sends PC, flashes
- `"pc_dec"` + pressed only → decrements, sends PC, flashes

`pc_values` is a 16-element array (one per MIDI channel), shared across all pc_inc/dec buttons on that channel.

Keytimes: `btn_state.advance_keytime()` is called before reading `state_cfg`, so per-state overrides are applied from `btn_config["states"][keytime_index]` via `get_button_state_config()`.

### Config Loading

`firmware/dev/core/config.py` handles config parsing. Key points:
- `get_display_config(config)` returns display settings with defaults (`"medium"` for all sizes)
- `get_usb_drive_name(config)` returns the validated USB volume label (calls `validate_usb_drive_name()`, defaults to `"MIDICAPTAIN"`)
- `get_dev_mode(config)` returns `bool(config.get("dev_mode", False))` — always safe to call even if the key is absent
- `validate_usb_drive_name(name)` enforces FAT32 label rules: uppercase, alphanumeric + underscore, max 11 chars; returns `"MIDICAPTAIN"` for empty/invalid input
- `STATE_OVERRIDE_FIELDS = ("cc", "cc_on", "cc_off", "note", "velocity_on", "velocity_off", "program", "pc_step", "color", "label")` — fields that can be overridden per keytime state
- Default button: `{"label": str(i+1), "cc": 20+i, "color": "white"}`

### USB Drive Behaviour (boot.py)

`boot.py` runs before `code.py` and before USB is fully initialized. This imposes a **critical ordering constraint**: `storage.disable_usb_drive()` must be called **before** any `storage.remount()` call (which initializes USB).

**Two-mode logic:**
```python
dev_mode   = get_dev_mode(cfg)          # from config.json
switch_held = not switch_1.value        # GP1, pull-up: LOW = pressed
enable_usb_drive = dev_mode or switch_held

if not enable_usb_drive:
    storage.disable_usb_drive()         # MUST be first

if enable_usb_drive:
    storage.remount("/", readonly=False, label=usb_drive_name)
```

**Why two `if` blocks instead of `if/else`**: the original `boot.py` (before custom drive names) never called `remount()`, so `if/else` was fine. Adding `storage.remount()` for custom labels introduced an ordering constraint: `disable_usb_drive()` must execute before any `remount()` call. Using two separate `if` blocks makes this ordering explicit in source — `disable` always appears above `remount`, preventing future refactors from accidentally reversing the calls.

**Boot sequence for config reads**: `boot.py` runs before normal `sys.path` is established. It manually inserts `/core` via `sys.path.insert(0, "/core")` to import `config.py`. If config loading fails (missing file, parse error), a bare `except Exception` swallows it and safe defaults are used.

---

## Key Files

| Path | Purpose |
|------|---------|
| `firmware/dev/code.py` | **Active**: Unified firmware with config, display, bidirectional MIDI |
| `firmware/dev/boot.py` | Disables autoreload; USB drive gated by `dev_mode` config flag or Switch 1 hold; applies custom drive label |
| `firmware/dev/config.json` | STD10 default config (button labels, CC numbers, colors, drive name, dev_mode) |
| `firmware/dev/config-mini6.json` | Mini6 template config (copy to device as config.json) |
| `firmware/dev/VERSION` | Firmware version (generated, gitignored) |
| `firmware/dev/core/config.py` | Config loading; `get_usb_drive_name()`, `validate_usb_drive_name()`, `get_dev_mode()`, `get_display_config()`; `STATE_OVERRIDE_FIELDS` |
| `firmware/dev/core/button.py` | `ButtonState` class: toggle/momentary mode, keytimes cycling |
| `firmware/dev/core/colors.py` | Color palette and `get_off_color()` utilities |
| `firmware/dev/devices/std10.py` | STD10 hardware constants |
| `firmware/dev/devices/mini6.py` | Mini6 hardware constants |
| `firmware/original_helmut/code.py` | Helmut's original firmware (reference only, DO NOT MODIFY) |
| `tools/deploy.sh` | Dev deploy to device (rsync, VERSION, device detection) |
| `docs/hardware-reference.md` | Verified hardware specs, auto-detection docs |
| `docs/screen-cheatsheet.md` | Serial console (screen) usage guide |
| `docs/emulator-setup.md` | Emulator setup guide (rp2040js-circuitpython) |
| `docs/plans/2026-01-23-custom-firmware-design.md` | Full design document |
| `.github/workflows/ci.yml` | CI: lint, syntax check (CP 7.x guards), build firmware zip |
| `emulator/setup.sh` | Download and configure emulator (one-time) |
| `emulator/run.sh` | Run firmware interactively in emulator |
| `emulator/test.sh` | Automated emulator tests |
| `.github/workflows/emulator-test.yml` | Emulator integration tests (manual/weekly) |
| `.github/workflows/release.yml` | Create GitHub Release on version tag |
| `config-editor/src/routes/+page.svelte` | App shell: device selector, save/reload/reset |
| `config-editor/src/lib/formStore.ts` | Form state, undo/redo, `updateField`, `normalizeConfig`, `loadConfig` |
| `config-editor/src/lib/types.ts` | TypeScript config interfaces — must stay in sync with Rust structs |
| `config-editor/src/lib/validation.ts` | Client-side validation; must mirror Rust validation in `config.rs` |
| `config-editor/src/lib/components/ButtonRow.svelte` | Per-button form row; `onUpdate` callback prop |
| `config-editor/src/lib/components/DeviceSection.svelte` | Device type, global channel, USB drive name, and dev mode fields |
| `config-editor/src-tauri/src/config.rs` | Rust config structs + validation + round-trip tests |
| `config-editor/src-tauri/src/commands.rs` | Tauri IPC commands: read/write/validate, path security |
| `config-editor/src-tauri/src/device.rs` | USB device detection and hot-plug watcher |

---

## Communication Style

- Be concise and technical
- Prefer working code over lengthy explanations
- When proposing changes, provide complete, runnable implementations
- Document decisions and trade-offs in commit messages or docs

## Pull Request Guidelines

- When making a PR, include a clear description of the change, the rationale, and any relevant context
- Reference related issues or design docs
- Ensure all CI checks pass before requesting review
- Reviewers should focus on correctness, readability, and maintainability
- Once a PR Title and description are fully filled out, don't change them — they serve as the source of truth for the change history and rationale. If you need to clarify or update information, add notes or comments to the existing description rather than rewriting it. This preserves the original context and decision-making process for future reference.
- Do not include details on changes made during iteration in the PR description. The description should reflect the final state of the code after all iterations, not the process of getting there. This keeps the change history clean and focused on the end result rather than the development process. That being said, any important discoveries or decisions made during iteration that are relevant to understanding the final code should be documented in the PR description or in linked design docs, but not as a step-by-step account of the iteration process.

### Pull Request Examples
- Read the file docs/PR_Examples/example1.md for an example of a well-structured PR description that provides clear context, rationale, and references to design documents. This style should be followed for all PRs to ensure clarity and maintainability of the project history.