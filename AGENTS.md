# Agent Instructions

## Sub-AGENTS Files

For detailed technical context, read the relevant sub-file before working in that area:

- **[firmware/AGENTS.md](firmware/AGENTS.md)** — CircuitPython practices, hardware reference, firmware patterns, CP 7.x restrictions, device variants
- **[config-editor/AGENTS.md](config-editor/AGENTS.md)** — Config editor architecture, schema-driven types, save flow, Tauri/Rust details
- **[.github/AGENTS.md](.github/AGENTS.md)** — CI/CD workflows, versioning, release process, deploy scripts, code signing

---

## Project Context

This repository creates **custom CircuitPython firmware** for Paint Audio MIDI Captain foot controllers — a generic, config-driven, bidirectional MIDI firmware suitable for diverse performance scenarios.

### Primary Goals
- **Bidirectional MIDI sync** — host controls LEDs/LCD state, device sends switch/encoder events
- **Config-driven mapping** — JSON configuration for MIDI assignments and UI layouts
- **Multi-device support** — STD10 (10-switch), Mini6 (6-switch), NANO4 (4-switch), DUO2 (2-switch), ONE1 (1-switch)
- **Hybrid state model** — local toggle for instant feedback, host-authoritative when it speaks
- **Rock-solid reliability** — NO unexpected resets during live performance; stability is paramount

### Reliability Philosophy

This is a **live performance tool**. The device must:
- **Never reset unexpectedly** — autoreload is disabled; changes require explicit reload
- **Never crash** — defensive coding, graceful error handling, no unhandled exceptions
- **Never lose state** — if host connection drops, device continues functioning locally
- **Never surprise the performer** — predictable behavior in all scenarios

---

## Code Attribution & Directory Structure

### ⚠️ Original Code Preservation
All code in `firmware/original_helmut/` is authored by **Helmut Keller** and must remain **untouched** with full attribution.

### Development Philosophy
Helmut's code was a starting point, not a constraint. We are free to completely refactor or rewrite any functionality. Build what makes sense for this project.

### Directory Layout

| Path | Purpose |
|------|---------|
| `firmware/original_helmut/` | Helmut Keller's original firmware — **DO NOT MODIFY** |
| `firmware/dev/` | Active development — refactored code goes here |
| `firmware/dev/devices/` | Device abstraction modules (std10, mini6, nano4, duo2, one1) |
| `firmware/dev/experiments/` | Throwaway experiments and proof-of-concepts |
| `firmware/dev/core/` | Core modules (button.py, config.py, colors.py, hid.py) |
| `firmware/dev/fonts/` | PCF display fonts (PTSans variants) |
| `firmware/dev/lib/` | CircuitPython libraries (CP 7.x `.mpy` format) |
| `config-editor/` | Config editor app (Tauri 2 + SvelteKit 5) |
| `tests/` | pytest test suite with CircuitPython hardware mocks |
| `docs/` | Architecture notes, MIDI protocol docs, hardware findings |
| `tools/` | Helper scripts (packaging, validation, deployment) |

New code belongs in `firmware/dev/` or new directories (never in `original_helmut/`).

---

## Key Files

| Path | Purpose |
|------|---------|
| `firmware/dev/code.py` | Unified firmware: config, display, bidirectional MIDI |
| `firmware/dev/boot.py` | Disables autoreload; USB drive gating; custom drive label |
| `firmware/dev/core/config.py` | Config loading, `get_usb_drive_name()`, `validate_usb_drive_name()`, `get_dev_mode()` |
| `firmware/dev/core/hid.py` | HID dispatch: `KEY_TABLE`, `MODIFIER_TABLE`, `dispatch_hid()` |
| `firmware/dev/core/button.py` | `ButtonState`: toggle/momentary mode, keytimes cycling |
| `firmware/dev/core/colors.py` | Color palette and `get_off_color()` |
| `firmware/dev/devices/{device}.py` | Per-device hardware constants |
| `config.schema.json` | JSON Schema (draft-07) — single source of truth for config format |
| `tools/deploy.sh` | Dev deploy to device (rsync, VERSION.txt, device detection) |
| `docs/hardware-reference.md` | Verified hardware specs, pin mappings |
| `docs/plans/2026-01-23-custom-firmware-design.md` | Full design document |
| `.github/workflows/ci.yml` | CI: lint, syntax check (CP 7.x guards), build firmware zip |
| `.github/workflows/release.yml` | Create GitHub Release on version tag |

---

## Development Practices

### Git Workflow
- **Trunk-based development** — work on `main`, use short-lived feature branches if needed
- Commit frequently with clear, descriptive messages

### Testing

Run all test suites from the repo root:
```bash
./tools/test-all.sh
```

Individual suites:
```bash
python3 -m pytest tests/                         # Python tests
cd config-editor/src-tauri && cargo test         # Rust tests
cd config-editor && npm run check                # TypeScript / Svelte
cd config-editor && npm run generate:types       # regenerate types from schema
```

### Linting

Lint is folded into `./tools/test-all.sh`, which runs `ruff` (Python) and `cargo clippy` (Rust) alongside the test suites. Run that script at the verification checkpoint — once before claiming completion or requesting review, not after every edit.

`pyproject.toml` configures ruff to ignore four rules that flag deliberate codebase patterns (`E402`, `E712`, `F401`, `F403`); see the comments in that file for rationale before adding new exceptions. `cargo clippy` runs warnings-only — there are two pre-existing warnings on untouched code that should be addressed in a separate cleanup pass, not silently muted.

To run lint alone (without the full test suite):
```bash
ruff check firmware/ tests/                                   # Python
cd config-editor/src-tauri && cargo clippy --lib --no-deps    # Rust
```

### Dependencies
- **`requirements-dev.txt`**: CI/dev tools (ruff, pytest)
- **`requirements-circuitpython.txt`**: On-device libraries for `circup install -r`

---

## Roadmap & Issue Tracking

Track features and bugs via [GitHub Issues](https://github.com/MC-Music-Workshop/midi-captain-max/issues) and [Projects](https://github.com/orgs/MC-Music-Workshop/projects/1/views/1).

### Future Work
- [ ] Separate USB vs DIN MIDI configuration
- [ ] Scripting / MIDI Transform Engine (config-driven rules triggering on incoming MIDI)
- [ ] CI workflow DRY: composite actions for duplicated Node.js setup steps
- [ ] Windows Signing Cert
- [ ] Custom display layouts
- [ ] SysEx protocol documentation
- [ ] Keytimes / multi-press cycling, double-press, long-press detection
- [ ] Pages / banks
- [ ] Firmware press-handler unit tests for select-mode (`handle_pc_select_press`, `handle_cc_select_press`, `update_select_group`, and the RX hooks in `_process_midi_msg`). Validator coverage exists; runtime coverage does not. Mock infrastructure in `tests/mocks/` should support this.
- [ ] Tighten `pyproject.toml` ruff ignores: `F401` is currently global; should be scoped via `[tool.ruff.lint.per-file-ignores]` so genuinely-unused imports in production code get caught. Test-mock re-exports under `tests/mocks/**` are the legitimate use.
- [ ] Decide encoder-push `mode: "select"` handling. Auto-generated TS now allows it on `EncoderPush.mode` (shared `ButtonMode` enum), but encoder push has no `select_group` field and the editor doesn't expose it. Options: separate `EncoderButtonMode` enum (without `Select`), explicit validator rejection, or document as silently allowed/no-op.
