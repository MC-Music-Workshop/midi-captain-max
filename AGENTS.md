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
- **Multi-device support** — STD10 (10-switch), Mini6 (6-switch), NANO4 (4-switch), DUO2 (2-switch), and ONE (1-switch) targets
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
| 5 | Multi-device support (STD10 + Mini6 + NANO4 + DUO2 + ONE) | ✅ Working |
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
| `firmware/dev/devices/` | Device abstraction modules (std10.py, mini6.py, nano4.py, duo2.py, one1.py) |
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
- **CI workflow** (`.github/workflows/ci.yml`): Runs on push to any branch AND on `v*` tag push
  - Lints code with Ruff (ignores E501, F401, E402 for CircuitPython compatibility)
  - Validates Python syntax
  - Writes `VERSION` file into firmware zip from git tag/describe
  - Runs pytest suite (`tests/`)
  - Uses `requirements-dev.txt` for dependencies
  - Builds Config Editor for macOS and Windows (Tauri + SvelteKit)
  - **Tag trigger is critical**: CI must run on tag push so `git describe` sees the tag and bakes the correct version into artifacts. Without this, artifacts get the pre-tag version (e.g., `1.8.0-rc1` instead of `1.8.0`).
  - **Docs-only PRs can't satisfy branch protection.** `ci.yml` uses `paths-ignore: ["**/*.md", "docs/**"]`, so docs-only changes run zero jobs. Branch protection's "required checks must pass" therefore stays unreported and the PR cannot auto-merge. Merge with `gh pr merge --admin` (reversible via revert). Long-term fix: promote the required status checks to an always-running "gate" job that short-circuits for docs-only.
  - **Firmware-zip artifact uses `archive: false`.** The zip payload is already compressed, so we skip GitHub's outer zip wrapper via `archive: false` in `build-zip`'s upload step. Saves ~3 s per CI run. `archive: false` is documented (`upload-artifact/action.yml#52`) to ignore the `name:` input and take the artifact name from the file's basename — so the stage-firmware-for-editor composite action receives a `version:` input and downloads by the same `midicaptain-firmware-<ver>.zip` formula. `release.yml` is untouched (its `find -name "midicaptain-firmware-*.zip"` still matches). Don't reintroduce `compression-level: 0` as an alternative — empirically tested 2026-04-21 (`51d08ba` → `ed73bef`), it made the artifact ~10% *larger* because the wrapper's metadata compresses even when the payload doesn't.
- **Release workflow** (`.github/workflows/release.yml`): Triggered by `v*` tags
  - Downloads artifacts from the CI run for the same commit (by SHA)
  - Polls for up to 30 minutes waiting for CI to complete (tag push triggers both workflows simultaneously)
  - Fails fast if CI fails or is cancelled
  - Creates GitHub Release with artifacts
  - Auto-detects alpha/beta for pre-release flag

#### Version Flow
- `git describe --tags --always` → strip `v` prefix and commit-distance suffix → SEMVER
- Examples: `v1.8.0` → `1.8.0`, `v1.8.0-rc1` → `1.8.0-rc1`, `v1.5.0-11-gabc1234` → `1.5.0`
- macOS build: uses SEMVER as-is (Tauri accepts semver pre-release identifiers like `1.8.0-rc1`)
- Windows build: WiX MSI rejects non-numeric pre-release identifiers, so a conversion step strips alpha chars: `1.8.0-rc1` → `1.8.0-1`
- **Tauri v2 requires strict semver** (3-part with optional pre-release) — 4-part versions like `1.8.0.1` are rejected by `tauri.conf.json` parser

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
- Config editor app in `config-editor/` (Tauri v2 + SvelteKit)
- **Build requires `svelte-kit sync`** before `vite build` — generates `.svelte-kit/tsconfig.json`. Without it, esbuild warns about missing tsconfig. The `build` npm script includes this.

---

## CircuitPython Practices

This project uses CircuitPython firmware deployed to hardware devices (ONE, DUO2, NANO4, Mini6, STD10). Always verify changes work with the target hardware constraints. For mpy-cross, use Adafruit's CircuitPython builds, NOT MicroPython pip packages.

- Target **CircuitPython 7.x** (7.3.1 verified on devices)
- Board identifies as `raspberry_pi_pico` (RP2040 MCU)
- USB CDC disconnects on reset — use auto-reconnect serial workflows
- `boot.py` uses GP1 as a mode pin (GP11 on DUO2/ONE1); readable at boot, usable as switch afterward
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
| `bytes.hex()` | `" ".join("%02x" % b for b in data)` |

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

### NANO4 (4-switch)
- 12 NeoPixels (4 switches × 3 LEDs) on GP7
- 4 switch inputs: GP1, `board.LED` (GP25), GP9, GP10 — all a subset of STD10/Mini6 pins
- 2×2 grid layout: TL, TR, BL, BR
- ST7789 240×240 display (same params as STD10/Mini6)
- No encoder or expression inputs

### DUO2 (2-switch)
- 6 NeoPixels (2 switches × 3 LEDs) on GP7
- 2 switch inputs: GP11 (KEY0, bottom), GP9 (KEY1, top)
- 4 DIP switches on GP0–GP3 for mode/page selection
- **No ST7789 display.** Instead a 3-digit 7-segment LCD driven via UART (GP4 TX, GP5 RX, 9600 baud) using a proprietary frame protocol: `[0xA5, seg1, seg2, seg3, 0x5A]` sent 3× with 40ms inter-frame delay. See `firmware/dev/devices/duo2.py` for the encoding.
- No encoder or expression inputs

### ONE1 (1-switch)
- 3 NeoPixels (1 switch × 3 LEDs) on GP7
- 1 switch input: GP11 (KEY0)
- 2 DIP switches on GP2–GP3 for mode/page selection
- Same UART segmented LCD as DUO2 (GP4/GP5, 9600 baud, identical 5-byte frame protocol)
- No encoder or expression inputs

### 5-pin DIN MIDI

- **TX pin**: `board.GP16`, **RX pin**: `board.GP17`, **baud**: `31250`, **timeout**: `0.003`
- `busio.UART` is available in CircuitPython 7.x; use `receiver_buffer_size=64` (512 is fine too)
- Wrap init in `try/except` — if UART is unavailable the firmware must still boot (`midi_serial = None`)
- The original Helmut firmware had DIN MIDI; the dev rewrite initially dropped it (now restored)
- **Pattern**: use a `midi_send(msg, channel=None)` helper that calls both `midi.send(msg, channel=channel)` (USB) and `midi_serial.send(msg, channel=channel)` (DIN), rather than duplicating every send site
- **⚠️ adafruit_midi channel API gotcha**: `midi.send(ControlChange(cc, val, channel=X))` does **NOT** work — the library ignores `msg.channel` and always uses `out_channel`. Channel must be passed to `send()`: `midi.send(ControlChange(cc, val), channel=X)`. This caused issue #95 where all MIDI output was stuck on channel 1. The `midi_send()` wrapper must accept and forward `channel`.
- **`in_channel`**: both USB and serial MIDI objects should use `in_channel=None` (receive all channels) for multi-channel bidirectional sync to work
- **MIDI Thru**: `handle_midi()` reads both ports; USB→DIN and DIN→USB forwarding happens there; both directions also drive LED/button state via `_process_midi_msg()`
- **Full bidirectionality**: a hardware device on the DIN port can control Captain LEDs/LCD exactly like a USB DAW host — `_process_midi_msg` is source-agnostic (`source` arg is debug-print only). CC value >63 = ON, ≤63 = OFF (`on_midi_receive` in `button.py`). NoteOn/Off and PC are also handled.
- **Keytimes caveat**: `on_midi_receive` sets boolean on/off state only — it does not advance the keytime slot. A host can illuminate the correct keytime color but cannot remotely cycle keytime positions.
- For now, USB and DIN outputs are always mirrored — separate configuration is deferred (complexity not worth it yet)

### Device Auto-Detection
Two-tier detection (config first, then hardware probe):
1. **Config-based**: reads `"device"` field from `/config.json` (`"one1"`, `"duo2"`, `"nano4"`, `"mini6"`, or `"std10"`)
2. **Hardware probe fallback**: checks STD10-exclusive switch pins (GP0/GP18/GP19/GP20) — if 3+ read HIGH with pull-ups, it's STD10; otherwise Mini6. Cannot distinguish Mini6, NANO4, DUO2, or ONE1 by probe alone.

**Note**: The old approach (probing `board.LED`/`board.VBUS_SENSE` for Mini6) was broken — GP25 exists on both devices, so everything was detected as Mini6. Always include `"device"` in config.json. This is especially important for NANO4, DUO2, and ONE1, which cannot be distinguished by hardware probe.

### Device Abstraction
Device-specific constants live in `firmware/dev/devices/`:
- `std10.py` — STD10 pin definitions and counts ✅
- `mini6.py` — Mini6 pin definitions ✅
- `nano4.py` — NANO4 pin definitions ✅
- `duo2.py` — DUO2 pin definitions (2 switches, 6 LEDs, UART segmented LCD) ✅
- `one1.py` — ONE1 pin definitions (1 switch, 3 LEDs, UART segmented LCD) ✅

### Adding a New Device Variant — Checklist

When adding a new device, update ALL of these files (copy-paste between variants is the #1 source of bugs — three review rounds caught missed files during DUO2/ONE1):

1. `firmware/dev/devices/{device}.py` — pin definitions, LED count, `switch_to_led()`
2. `firmware/dev/config-{device}.json` — template config
3. `firmware/dev/code.py` — device detection allow-list + module import block
4. `firmware/dev/boot.py` — boot switch pin if different from GP1
5. `config-editor/src-tauri/src/config.rs` — `DeviceType` enum + button count match + validation (uses `!= Std10` for encoder/expression)
6. `config-editor/src-tauri/src/device.rs` — `is_midi_captain_config` + `parse_midi_captain_config` match arms + docstrings
7. `config-editor/src/lib/types.ts` — `DeviceType` union
8. `config-editor/src/lib/formStore.ts` — all 4 device maps (`DEVICE_BUTTON_COUNT`, `DEVICE_HAS_ENCODER`, `DEVICE_HAS_EXPRESSION`, `DEVICE_HAS_TFT`)
9. `config-editor/src/lib/validation.ts` — device-specific constraints
10. `config-editor/src/lib/components/DeviceSection.svelte` — dropdown option + help text
11. `config-editor/src/lib/components/ButtonsSection.svelte` — `DEVICE_BUTTON_NAMES`
12. `tools/deploy.sh` — `VALID_DEVICES`, config scan loop, config selection, fallback deploy
13. `tools/deploy.ps1` — `ValidateSet`, config scan, config selection, fallback deploy (must stay at parity with `.sh`)
14. `.github/workflows/ci.yml` — mpy-cross compilation loop
15. `docs/hardware-reference.md` — full hardware section (don't copy-paste GPIO tables from other devices without adjusting!)
16. `AGENTS.md` — device lists, file tables, detection docs
17. Rust + device.rs tests — deserialization and `is_midi_captain_config` tests for the new type

**Tip:** grep for an existing device name (e.g., `duo2`) across the repo to catch any additional references.

### Reverse Engineering New Device Variants

Follow this sequence (proven on Mini6, NANO4, DUO2, and ONE):

1. **Pin scanner** — scan all GPIO pins as digital inputs with pull-ups, print which go LOW on each switch press
2. **NeoPixel probe** — light LEDs one at a time on GP7 to find count and chain order, then groups of 3 for per-switch mapping
3. **DIP switch probe** — if GPIO scan shows pins strongly pulled LOW at baseline, test if flipping DIP switches changes them (DUO2/ONE have DIP switches on GP0-GP3)
4. **Display discovery** — try ST7789 first, but if it fails (`ImportError` or no response), the device may have a segmented LCD via UART or other protocol. Use OEM module inspection (step 5).
5. **OEM module inspection** — the most powerful technique for unknown protocols. Write a `code.py` that `import`s the OEM module, catches `KeyboardInterrupt`, then inspects `sys.modules` to dump the module's globals (UART objects with `.baudrate`, display buffers, digit encodings). This revealed the DUO2's proprietary UART display protocol when all common protocols (TM1637, HT1621, MAX7219) failed.

Scripts go in `firmware/dev/experiments/` and get deployed as `code.py` on the device. Don't assume pin mappings or display types from other variants.

### Adding a New Device Variant — Checklist

Update ALL of these files (missed items caused real bugs across DUO2/ONE1 work):

1. `firmware/dev/devices/{device}.py` — pin definitions
2. `firmware/dev/config-{device}.json` — template config
3. `firmware/dev/code.py` — device detection allow-list + module import block
4. `firmware/dev/boot.py` — boot switch pin if different from GP1
5. `config-editor/src-tauri/src/config.rs` — `DeviceType` enum + button count match + validation
6. `config-editor/src-tauri/src/device.rs` — `is_midi_captain_config` + `parse_midi_captain_config` match arms
7. `config-editor/src/lib/types.ts` — `DeviceType` union
8. `config-editor/src/lib/formStore.ts` — all device capability maps (button count, encoder, expression, TFT)
9. `config-editor/src/lib/validation.ts` — device-specific constraints
10. `config-editor/src/lib/components/DeviceSection.svelte` — dropdown + help text
11. `config-editor/src/lib/components/ButtonsSection.svelte` — `DEVICE_BUTTON_NAMES` + `isDisabled`
12. `tools/deploy.sh` — `VALID_DEVICES`, config scan loop, config selection, fallback deploy
13. `.github/workflows/ci.yml` — mpy-cross compilation loop
14. `docs/hardware-reference.md` — full hardware section
15. `AGENTS.md` — device lists, file tables, detection docs

**Tip:** Grep for an existing device name (e.g., `duo2`) across the repo to find any additional references.

---

## Testing Strategy

### Running All Tests

From the repo root, run every test suite and the type-freshness check in one go:

```bash
./tools/test-all.sh
```

This runs pytest, cargo test, svelte-check, regenerates types from the schema, and fails if `types.generated.ts` ended up out of date.

Individual suites:

```bash
python3 -m pytest tests/                                    # 232 Python tests
python3 -m pytest tests/test_schema.py -v                   # schema validation only
cd config-editor/src-tauri && cargo test                    # 32 Rust tests
cd config-editor && npm run check                           # TypeScript / Svelte
cd config-editor && npm run generate:types                  # regenerate types from schema
```

The `generate:types` step is also enforced in CI: if `types.generated.ts` differs after running it, the build fails with instructions to commit the regenerated file.

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

All distribution paths must include the same set of files and write the `VERSION` file. If you add a new directory under `firmware/dev/`, you must add it to **all** of these:
1. `tools/deploy.sh` — dev deploy via rsync (also writes `VERSION` to device and local `firmware/dev/`)
2. `.github/workflows/ci.yml` — firmware zip (`build-zip` job, writes `VERSION` from lint job output)
3. `config-editor/src-tauri/resources/firmware/` — bundled into Config Editor app at CI build time via the `firmware-zip` artifact; for local dev runs use `tools/bundle-firmware-for-dev.sh`

**`tools/deploy.ps1`** is the Windows PowerShell equivalent of `deploy.sh`. Both scripts must stay at feature parity — when adding device types, config files, flags, or changing deploy logic, update **both** scripts. The ps1 uses `[ValidateSet()]` for device type validation and `Sync-File`/`Sync-Directory` helpers instead of rsync.

Device config files (`config*.json`) are included dynamically via glob in both paths, so adding a new device config does not require editing either file.

```bash
./tools/deploy.sh                   # Quick deploy (sync firmware, preserve config)
./tools/deploy.sh --device nano4    # First-time setup (config + libs + firmware)
./tools/deploy.sh --reset-config    # Reset config.json to template defaults
./tools/deploy.sh --install         # Re-check/install CircuitPython libraries
./tools/deploy.sh --eject           # Deploy + eject (forces clean reload)
./tools/deploy.sh /Volumes/MIDICAPT # Custom mount point
```

### Desktop Testing (Unit)
- **pytest** with CircuitPython hardware mocks in `tests/mocks/`
- Mocks cover: `board`, `digitalio`, `neopixel`, `displayio`, `busio`, `rotaryio`, `analogio`, `usb_midi`, `terminalio`
- Firmware behavior tests: `test_button_state.py`, `test_config.py`, `test_colors.py`, `test_neopixel_mock.py`, `test_switch_mock.py`, `test_usb_drive_name.py`
- Schema-driven tests (require `jsonschema` from `requirements-dev.txt`):
  - `test_schema.py` — validates all shipped configs against `config.schema.json` plus negative tests for every constraint type
  - `test_config_cross_fields.py` — rules JSON Schema can't express (button count vs device, encoder/expression device support, min/max/initial relationships, states/keytimes alignment)
  - `test_python_schema_sync.py` — AST-walks `core/config.py` to catch firmware reading fields not defined in the schema; also asserts `STATE_OVERRIDE_FIELDS` and `VALID_TYPES` match the schema
- Run: `python3 -m pytest tests/` from repo root

### Emulator Testing (Wokwi)

Headless firmware testing using **Wokwi CLI** — runs actual CircuitPython 7.3.3 on a simulated RP2040.

#### How it works
`wokwi-cli` uploads a UF2 to Wokwi's cloud simulator and streams serial output back. The key challenge: the CLI does **not** inject project files into CircuitPython's flash filesystem (that's a browser-only feature). The solution is an **all-in-one UF2** that bundles the CP runtime + a FAT12 filesystem containing our firmware.

`emulator/build-uf2.py` creates this bundle:
1. Formats a 1MB FAT12 image using `pyfatfs` (pure Python, cross-platform)
2. Populates it with `code.py`, `boot.py`, `config.json`, `core/`, `devices/`, `lib/`, `fonts/`
3. Converts the FAT image to UF2 blocks at flash offset `0x10100000`
4. Concatenates with the CircuitPython 7.3.3 firmware UF2

#### Usage
```bash
pip install pyfatfs                         # one-time
./emulator/setup.sh                         # downloads CP UF2, builds firmware-bundle.uf2
export WOKWI_CLI_TOKEN=your_token           # from https://wokwi.com/dashboard/ci
./emulator/test.sh                          # automated: --expect-text "MIDI CAPTAIN" --fail-text "Traceback"
./emulator/run.sh                           # interactive
```

#### Directory layout
```
emulator/
├── build-uf2.py          # Builds all-in-one UF2 (requires pyfatfs)
├── setup.sh              # Downloads CP UF2, runs build-uf2.py
├── test.sh               # wokwi-cli automated test
├── run.sh                # wokwi-cli interactive mode
├── wokwi.toml            # Points firmware at firmware-bundle.uf2
├── diagram.json          # STD10 hardware model for Wokwi simulator
├── test-boot.yaml        # Automation scenario (button press simulation, alpha)
├── configs/              # Test configs using correct firmware schema
├── firmware-bundle.uf2   # Generated — gitignored
└── circuitpython.uf2     # Downloaded — gitignored
```

#### What it can test
Firmware boot, config loading/parsing, device detection, button/encoder/expression init, MIDI message sending, display init (font loading), main loop execution.

#### What it cannot test
NeoPixel/display visual rendering (code runs, no visual output), GP23/24/25 buttons (internal Pico pins not exposed in Wokwi), real USB MIDI communication.

#### Gotchas
- **`wokwi-cli` requires `firmware` field** in `wokwi.toml` — it's a hard requirement, not optional for CircuitPython
- **GP23, GP24, GP25 are not available** on Wokwi's `wokwi-pi-pico` — valid pins are GP0–GP22 and GP26–GP28. The MIDI Captain PCB uses these internal pins for 3 switches; they can't be wired in the diagram but the firmware runs fine (switches float HIGH with pull-ups)
- **NeoPixel part type** is `wokwi-neopixel` (not `wokwi-neopixel-ring`); pins are `DIN`/`DOUT`/`VDD`/`VSS` (not `VCC`/`GND`)
- **CircuitPython filesystem is read-only from serial** — `storage.remount()` fails with `Cannot remount '/' when visible via USB` unless called from `boot.py` before USB init. This is why file injection via mpremote/REPL doesn't work.
- **`pyfatfs` API**: must create the image file first (`f.truncate(size)`), then call `PyFat.mkfs()`, then open with `PyFatFS()`. There is no `create=True` parameter.
- **UF2 block renumbering**: when concatenating two UF2s, all `block_no` and `total_blocks` fields must be rewritten across both halves
- **Free tier**: 50 CI minutes/month — sufficient for weekly runs, not per-push. Pro is $25/seat/mo for 2,000 minutes.
- **`rp2040js-circuitpython` is a dead end** — has no CLI argument parsing, no `--image`/`--fs` flags, no filesystem injection. PR #33 was based on non-existent features.

### Rust Tests (Config Editor)
Unit tests for the Tauri backend live in `config-editor/src-tauri/src/` (in `config.rs` and `device.rs`). Notably, `test_roundtrip_all_shipped_configs` parses every `firmware/dev/config*.json` file as both `serde_json::Value` and `MidiCaptainConfig`, then asserts every key survives serialize → deserialize through the typed struct. This catches "Rust struct missing a field" silent data loss for any new shipped config without needing a per-feature test.

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

**Notarization 403 "agreement missing or expired":** Apple periodically updates the Developer Program License Agreement and freezes notarization until the team's Account Holder accepts the new terms. The CI step fails with `HTTP status code: 403. A required agreement is missing or has expired`. Fix: Account Holder logs into [App Store Connect](https://appstoreconnect.apple.com), accepts pending agreements (usually shown as a banner or under Agreements/Tax/Banking), then re-runs the failed CI job. No code change needed.

### GPG Signing Key for Linux distributions

In use, details pending

---

## Licensing

**Copyright (c) 2026 Maximilian Cascone** — All rights reserved.

This firmware is proprietary software. You may use it freely for personal or commercial purposes (performances, recordings, etc.), but ***you may not sell, redistribute modified versions, or bundle it without permission***.

**Attribution to Helmut Keller:** This project was inspired by firmware originally created by Helmut Keller (https://www.helmutkelleraudio.de/). The original reference code in `firmware/original_helmut/` remains his work, preserved unmodified with his permission:

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

### Future
- [x] 5-pin DIN MIDI output + thru (mirrored from USB; GP16 TX / GP17 RX / 31250 baud) — 2026-03-13
- [ ] Separate USB vs DIN MIDI configuration (deferred — adds complexity, low priority)
- [ ] **Scripting / MIDI Transform Engine** — allow users to define rules that trigger on incoming MIDI and produce outgoing MIDI or internal actions. The Captain becomes a standalone MIDI brain: transpose, remap, filter, merge, split, and transform MIDI between DIN and USB without a computer. Analogous to Gig Performer GP Script, Bome MIDI Translator, MIDIStroke, LoopBe, etc. — but running on the device itself.
  - Config-driven first: a `scripts` or `rules` section in `config.json` mapping trigger conditions to actions (e.g. `{ "on": {"type": "cc", "cc": 5, "value": ">63"}, "send": {"type": "pc", "program": 2} }`)
  - Scripting language second (higher complexity): a minimal interpreted DSL in CircuitPython (line-by-line eval or pre-compiled to a simple bytecode). Look at GP Script / Pawn / Lua as inspiration for syntax.
  - Marketing angle: *"The Captain is the brain of your rig"* — not just a footswitch, but a real-time MIDI processor and rules engine that replaces desktop MIDI utility apps on stage.
- [ ] CI workflow DRY: `Setup Node.js` + `Install frontend dependencies` duplicated between `build-config-editor-macos` and `build-config-editor-windows` — could be a composite action
- [ ] Release workflow DRY: find/rename/warn pattern in `Prepare release assets` repeats 3× (DMG, MSI, NSIS) — could be a shell function
- [ ] Windows Signing Cert
- [x] NANO4 device support (4-switch variant) — hardware probed 2026-04-01, device module + firmware + config editor
- [x] DUO2 device support (2-switch variant) — UART segmented LCD reverse-engineered, device module + firmware + config editor
- [x] ONE1 device support (1-switch variant) — same UART display protocol as DUO2, device module + firmware + config editor
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
| `config.schema.json` | JSON Schema (draft-07) — single source of truth for the config format |
| `config-editor/src/lib/types.generated.ts` | Auto-generated TypeScript types from `config.schema.json` (run `npm run generate:types`) |
| `config-editor/src/lib/types.ts` | Re-exports generated types + UI-only types (`DetectedDevice`, `ConfigError`, `BUTTON_COLORS`) |
| `config-editor/src/lib/validation.ts` | Client-side validators; `validateConfig()` called before every save |
| `config-editor/src/lib/api.ts` | Tauri `invoke()` wrappers for all IPC calls |
| `config-editor/src/lib/components/ConfigForm.svelte` | Toolbar (Undo/Redo/View JSON/Save), keyboard shortcuts |
| `config-editor/src/lib/components/ButtonRow.svelte` | Per-button fields; uses `onUpdate` callback prop |
| `config-editor/src/lib/components/ButtonsSection.svelte` | Iterates buttons, wires `handleButtonUpdate → updateField` |
| `config-editor/src/lib/components/DisplaySection.svelte` | Display text size settings |
| `config-editor/src-tauri/src/config.rs` | Rust config structs + validation; must mirror `config.schema.json` |
| `config-editor/src-tauri/src/commands.rs` | Tauri commands: read/write/validate config, restart device, path security |
| `config-editor/src-tauri/src/device.rs` | USB device detection and watcher (cross-platform) |

### Serial Soft-Reboot

`restart_device` sends Ctrl-C (`0x03`) + Ctrl-D (`0x04`) over serial to trigger a CircuitPython soft reload. The USB drive stays mounted — no eject or power cycle needed.

- **Port discovery**: Filters `serialport::available_ports()` by Adafruit VID (`0x239A`). Currently requires exactly one Adafruit device connected; multi-device support (correlate by USB serial number) is planned.
- **macOS cu.*/tty.* deduplication**: Each USB serial device appears as both `/dev/cu.*` and `/dev/tty.*`. The code deduplicates by preferring `cu.*` (doesn't block waiting for carrier detect). Without this, the VID filter finds 2 ports for 1 device and hits the multi-device error.
- **Timing**: 500ms delay between Ctrl-C and Ctrl-D for REPL initialization. Verified working on macOS. Not yet tested on native Windows (VM USB passthrough introduces unreliable latency).
- **Thread blocking**: `restart_device` uses `thread::sleep`. This is fine because Tauri commands run on a thread pool. If this ever moves to `async`, the sleep must become `tokio::time::sleep`.
- **Serial port busy**: If another program (e.g., `tio`, `screen`, Arduino Serial Monitor) has the port open, the open will fail with "Device or resource busy". The frontend shows manual restart instructions as fallback.
- **Fallback**: If serial port is unavailable (port busy, multiple devices, etc.), the frontend shows manual restart instructions.

### Eject Device

`eject_device` safely unmounts the device volume. Cross-platform:
- **macOS**: `diskutil eject`
- **Linux**: `gio mount -u` with `umount` fallback (not `udisksctl` — it expects block devices, not mount points)
- **Windows**: PowerShell `Shell.Application` COM object `.InvokeVerb("Eject")` — same mechanism as Explorer's "Eject" context menu

### Tauri Windows Installer

`tauri.conf.json` `bundle.windows.nsis.installMode` controls install location:
- `"perUser"` (default): installs to `AppData` — deep, hard to find
- `"both"`: prompts user to choose per-machine (Program Files) or per-user, defaulting to Program Files

### Critical: Schema-Driven Config Types

**Single source of truth**: `config.schema.json` (JSON Schema draft-07) at the repo root defines every config field, type, constraint, and default. When adding or changing a config field:

1. **Edit `config.schema.json`** — this is the only place where the config format is defined
2. **Regenerate TypeScript types**: `cd config-editor && npm run generate:types` — produces `src/lib/types.generated.ts`
3. **Update the Rust struct** in `config-editor/src-tauri/src/config.rs` — add the matching field with `#[serde(skip_serializing_if = "Option::is_none")]`
4. **Update Python firmware** in `firmware/dev/core/config.py` if the field is used at runtime

**CI validates** that all `firmware/dev/config*.json` files pass the schema, and that `types.generated.ts` is up to date.

**Serde still silently drops unknown fields** — if a field exists in TypeScript but not in the Rust struct, it is deserialized away and the re-serialized output omits it. Round-trip tests in `config.rs` catch this. The schema is the reference the Rust structs are held against.

**The schema `title` field is load-bearing.** `json-schema-to-typescript` derives the root TypeScript interface name from `title` (PascalCased). Today: `"MIDI Captain Config"` → `MIDICaptainConfig`. Changing the title also renames the interface and breaks every import in `types.ts`. Keep the title short and stable; put product/branding text in `description` where it has no mechanical effect.

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

`config.schema.json` is the canonical reference for all constraints. Client-side validation (`validation.ts`) and server-side Rust validation (`config.rs`) should both match the schema. Key constraints:
- **Button labels**: max 6 chars, pattern `[\w \-]+`
- **Encoder/expression labels**: max 8 chars
- **Channels**: 0-15 (displayed 1-16)
- **MIDI bytes** (cc, note, program, velocity, etc.): 0-127
- **pc_step**: 1-127
- **keytimes**: 1-99
- **flash_ms**: 50-5000

**Cross-field rules** that JSON Schema can't express (enforced by Rust + verified by `tests/test_config_cross_fields.py`):
- Button array length must match device type (std10=10, mini6=6, nano4=4, duo2=2, one1=1)
- Encoder and expression are STD10-only
- `encoder.initial` must be in `[encoder.min, encoder.max]`
- `expression.max >= expression.min`
- `states.length` should match `keytimes` when `states` is present

### `mode` vs `off_mode` Per Button Type

From firmware `code.py`:
- **`mode` (toggle/momentary)**: used by CC and Note types only. PC types only fire on `pressed`, so mode is irrelevant. GUI shows Switch Mode only for `isCC || isNote`.
- **`off_mode` (dim/off)**: LED appearance when button is "off" — applies to all types. GUI always shows it.

### Accessibility Conventions

The config editor is held to **0 svelte-check warnings**. When adding form controls:

- Every `<label>` must associate with its control. Use `<label for="x">…</label>` paired with `id="x"` on the input. The wrap-style `<label>…<input/></label>` is also fine.
- For multi-instance components (rendered N times, like `ButtonRow`), derive unique IDs from the prop index. `ButtonRow` exposes `fieldId(field)` and `stateFieldId(si, field)` helpers — keep using them when adding fields.
- Use Svelte 5 event syntax: `onclick`, `onblur`, `onchange` — never `on:click` etc.
- Modal dialogs need `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, `tabindex="-1"`, and an Escape key handler.
- Backdrops with click handlers need `role="presentation"` + `tabindex="-1"` + an `onkeydown` handler (Enter/Space to activate).
- If a `$state` variable intentionally captures a prop's initial value (like `Accordion.svelte`'s `defaultOpen`), document the intent and use `// svelte-ignore state_referenced_locally`.

---

## Config JSON Schema

The config format is fully defined in [`config.schema.json`](config.schema.json) (JSON Schema draft-07). This is the single source of truth — see "Schema-Driven Config Types" above for the workflow when adding fields.

**`usb_drive_name`** — label applied to the FAT32 volume when USB is enabled. Defaults to `"MIDICAPTAIN"`. Configurable in the GUI "Device Settings" section. Validation rules (enforced by `validate_usb_drive_name()` in `core/config.py`): max 11 chars, uppercase alphanumeric + underscore only, auto-uppercased, special chars stripped, empty/all-invalid falls back to `"MIDICAPTAIN"`.

Tooling support for custom names:
- **`deploy.sh`** reads `usb_drive_name` from `config.json`, `config-one1.json`, `config-duo2.json`, `config-mini6.json`, and `config-nano4.json` and adds them to the mount-point search. Candidate order: `CIRCUITPY`, `MIDICAPTAIN`, then any `usb_drive_name` values found in local configs. Checked under `/Volumes/`, `/media/$USER/`, `/run/media/$USER/`.
- **GUI config editor** detects devices by volume name *and* config content. Known names (`CIRCUITPY`, `MIDICAPTAIN`) are always accepted. Custom-named volumes are accepted only when the config.json inside them (a) has a known `"device"` value (`"std10"`, `"mini6"`, `"nano4"`, `"duo2"`, or `"one1"`), and (b) the `usb_drive_name` in that config matches the actual volume name (case-insensitive). This cross-check prevents a stray config.json on an unrelated volume from being treated as a device. The same cross-check applies in `validate_device_path()` (path security gate in `commands.rs`).

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
    handle_midi()       # RX: USB + DIN; thru forwarding; update LED state
    handle_switches()   # TX: scan footswitches, dispatch MIDI on change
    update_pc_flash_timers()
    if HAS_ENCODER:
        handle_encoder_button()
        handle_encoder()
    if HAS_EXPRESSION:
        handle_expression()
```

No sleep — runs as fast as possible. Timing-sensitive code must use `time.monotonic()`.

### MIDI Output Pattern

All outgoing MIDI goes through `midi_send(msg)` which writes to both USB and 5-pin DIN simultaneously. Never call `midi.send()` directly from handler functions — always use `midi_send()`.

`handle_midi()` is split into:
- `_process_midi_msg(msg, source)` — updates LED/button state from any received message (source-agnostic)
- `handle_midi()` — reads USB and DIN ports, calls `_process_midi_msg`, handles thru forwarding

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
| `firmware/dev/config-one1.json` | ONE template config (copy to device as config.json) |
| `firmware/dev/config-duo2.json` | DUO2 template config (copy to device as config.json) |
| `firmware/dev/config-mini6.json` | Mini6 template config (copy to device as config.json) |
| `firmware/dev/config-nano4.json` | NANO4 template config (copy to device as config.json) |
| `firmware/dev/VERSION` | Firmware version (generated, gitignored) |
| `firmware/dev/core/config.py` | Config loading; `get_usb_drive_name()`, `validate_usb_drive_name()`, `get_dev_mode()`, `get_display_config()`; `STATE_OVERRIDE_FIELDS` |
| `firmware/dev/core/button.py` | `ButtonState` class: toggle/momentary mode, keytimes cycling |
| `firmware/dev/core/colors.py` | Color palette and `get_off_color()` utilities |
| `firmware/dev/devices/std10.py` | STD10 hardware constants (10 switches, encoder, expression, ST7789 display) |
| `firmware/dev/devices/mini6.py` | Mini6 hardware constants (6 switches, ST7789 display) |
| `firmware/dev/devices/nano4.py` | NANO4 hardware constants (4 switches, ST7789 display) |
| `firmware/dev/devices/duo2.py` | DUO2 hardware constants (2 switches, DIP switches, UART segmented LCD) |
| `firmware/dev/devices/one1.py` | ONE1 hardware constants (1 switch, DIP switches, UART segmented LCD) |
| `firmware/original_helmut/code.py` | Helmut's original firmware (reference only, DO NOT MODIFY) |
| `tools/deploy.sh` | Dev deploy to device (rsync, VERSION, device detection) |
| `docs/hardware-reference.md` | Verified hardware specs, auto-detection docs |
| `docs/screen-cheatsheet.md` | Serial console (screen) usage guide |
| `docs/plans/2026-01-23-custom-firmware-design.md` | Full design document |
| `.github/workflows/ci.yml` | CI: lint, syntax check (CP 7.x guards), build firmware zip |
| `.github/workflows/release.yml` | Create GitHub Release on version tag |
| `config-editor/src/routes/+page.svelte` | App shell: device selector, save/reload/reset |
| `config-editor/src/lib/formStore.ts` | Form state, undo/redo, `updateField`, `normalizeConfig`, `loadConfig` |
| `config.schema.json` | JSON Schema (draft-07) — single source of truth for config format |
| `config-editor/src/lib/types.generated.ts` | Auto-generated TypeScript types from schema (`npm run generate:types`) |
| `config-editor/src/lib/types.ts` | Re-exports generated types + UI-only types (`DetectedDevice`, `ConfigError`, `BUTTON_COLORS`) |
| `config-editor/src/lib/validation.ts` | Client-side validation; must mirror Rust validation in `config.rs` |
| `config-editor/src/lib/components/ButtonRow.svelte` | Per-button form row; `onUpdate` callback prop |
| `config-editor/src/lib/components/DeviceSection.svelte` | Device type, global channel, USB drive name, and dev mode fields |
| `config-editor/src-tauri/src/config.rs` | Rust config structs + validation + round-trip tests; must mirror `config.schema.json` |
| `config-editor/src-tauri/src/commands.rs` | Tauri IPC commands: read/write/validate, path security |
| `config-editor/src-tauri/src/device.rs` | USB device detection and hot-plug watcher |

---

## CI/Release Process

### Release Workflow

Releases use **draft releases** for pre-publish testing:

1. Push tag `v1.x.0` (CI must trigger on tags so `git describe` returns clean version for Tauri binary)
2. CI builds artifacts with clean version baked in
3. Release workflow waits for CI via `gh run watch --exit-status`, then creates a **draft** release
4. Download and test draft artifacts
5. Publish via GitHub UI when satisfied; delete draft + tag if not

**Tauri binary versions are baked at build time** (in `tauri.conf.json` via jq patch before `cargo tauri build`). They cannot be patched post-build due to code signing. This is why CI must run on the tag — the version string comes from `git describe`.

**Beta tags (`v1.x.0-betaN`) are usually unnecessary** — the draft release IS the test mechanism. Only use beta tags when (a) you expect multiple test cycles before final, or (b) you want a *published* (non-draft) beta release for external testers. For solo dev, tag `v1.x.0` directly, test the draft, publish when ready.

**Promoting a beta to final requires re-tagging the same commit.** Tauri binaries and the firmware `VERSION` file have the version string baked in at build time. If you tagged `v1.10.0-beta1` and want to ship as `v1.10.0`, tag the same commit as `v1.10.0` and let CI rebuild — otherwise the published artifacts will still say `1.10.0-beta1` internally.

### Merging Release Branches

**Always use fast-forward merge** to keep the tag on main's history:
```bash
git checkout main
git merge --ff-only <branch>
git push
```
GitHub's "Rebase and merge" UI option **rewrites commit SHAs** even when a fast-forward is possible, causing the tag to point to a commit that's no longer on main. This is a GitHub UI limitation — it always replays commits, never fast-forwards.

### CI Architecture

- **CI triggers**: branch pushes + tag pushes (`v*`). Tags needed for clean version injection.
- **Release triggers**: tag pushes only (`v*`). Creates draft releases.
- **Artifact flow**: CI uploads (`actions/upload-artifact@v7`), release downloads (`actions/download-artifact@v7`). These are different actions — don't confuse them (easy mistake).
- **Config validation**: The `lint` job validates all `firmware/dev/config*.json` files against `config.schema.json` (via `pytest` + `jsonschema`) and checks that `types.generated.ts` is up to date.
- **Firmware VERSION patching**: Release workflow patches `/VERSION` inside the firmware zip with the clean tag, since the CI-built VERSION contains a `git describe` string.
- **Linux CI deps**: `libudev-dev` required by the `serialport` crate. Cached via `awalsh128/cache-apt-pkgs-action`.

### Deploy Scripts

`tools/deploy.sh` and `tools/deploy.ps1` share the same deploy order and progress style:
- Per-file/directory labels with `(no changes)` when nothing was updated
- Shows current firmware version on device and incoming version at start
- `sync_dir` / `sync_file` helpers (bash) wrap rsync and strip itemize-changes prefixes

---

## Memory & Knowledge Persistence (Guiding Principle)

**Always write findings to memory — never relearn something twice.**

- After any investigation, bug fix, or feature implementation, record what was discovered in `AGENTS.md` under the relevant section.
- If a finding is generic enough to apply across all repos (workflow insight, platform quirk, tooling pattern), also write it to `~/.claude/CLAUDE.md` (global persona memory).
- Update existing sections rather than appending stale duplicates — keep entries current and accurate.
- This applies to: hardware pin confirmations, CircuitPython quirks, architectural decisions, things that were broken and why, things tried that didn't work, and any non-obvious implementation detail.

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