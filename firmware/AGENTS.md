# Firmware Agent Instructions

## CircuitPython Practices

Target **CircuitPython 7.x** (7.3.1 verified on devices). Board identifies as `raspberry_pi_pico` (RP2040 MCU).

- USB CDC disconnects on reset — use auto-reconnect serial workflows
- `boot.py` uses GP1 as a mode pin (GP11 on DUO2/ONE1); readable at boot, usable as switch afterward
- Autoreload typically disabled for performance; enable temporarily for rapid iteration
- For mpy-cross, use Adafruit's CircuitPython builds, NOT MicroPython pip packages

### Version Compatibility

| Feature | CP 7.x | CP 8.x+ |
|---------|--------|---------|
| Disable autoreload | `supervisor.disable_autoreload()` | `supervisor.runtime.autoreload = False` |

**TODO**: When upgrading to CP 8.x+, update `boot.py` to use `supervisor.runtime.autoreload = False`.

### Bundle libs are `.mpy` v5 (CP 7-compatible)

`firmware/dev/lib/` ships `.mpy` files in format v5, loadable by CP 7.x. To verify before adding a new lib: `xxd <file>.mpy | head -1` — the second byte is the format version (`05` = v5 = CP 7.x; `06` = v6 = CP 8.x+, will fail on CP 7).

### Never pass `circup install --py`

`tools/deploy.{sh,ps1}` deliberately omit `--py`. With `--py`, `circup` installs source `.py` over the bundle's `.mpy`, so both forms coexist in `/lib`. CP's resolution is version-dependent and the `.py` source often pulls in modules the runtime doesn't have (e.g. `busdisplay` is CP 9-only) — this bricked a real CP 7.3.1 NANO4.

### Automating CircuitPython REPL via serial

Used by the GUI installer's pre-flight halt + post-install soft-reboot, and by `restart_device`:

- **Ctrl-C halts `code.py`** and prints "Press any key to enter the REPL". CP _consumes_ the next inbound byte as that keypress. Always send a sacrificial CRLF after Ctrl-C before real commands — otherwise the first byte of your command gets eaten.
- **REPL is line-mode**: only executes a buffered line on CRLF (`\r\n`). Always end commands with `\r\n`.
- **Multi-line `try`/`except` doesn't paste cleanly** — use single-line semicolon-joined statements.
- **Soft reboot = Ctrl-D** after Ctrl-C. Re-runs `boot.py` + `code.py`, also re-enables autoreload.

### CP 7.x Syntax Restrictions (CRITICAL)

These pass `py_compile` and `pytest` on desktop Python but **crash on device boot** with `SyntaxError`:

| Banned Construct | Example | Use Instead |
|------------------|---------|-------------|
| Dict unpacking in literals | `{**cfg, "key": val}` | Manual loop: `for k,v in d.items(): r[k] = v` |
| Walrus operator | `if (n := len(x)) > 0:` | Separate assignment |
| `match`/`case` | `match x: case 1:` | `if`/`elif` |

**CI enforces this** via the "CircuitPython 7.x compatibility guard" step in `ci.yml`.

### Missing `str` Methods in CP 7.x

These work on desktop Python and pass all tests, but raise `AttributeError` at runtime on device:

| Missing method | Use Instead |
|----------------|-------------|
| `str.isalnum()` | `('A' <= c <= 'Z') or ('0' <= c <= '9')` (after `.upper()`) |
| `str.isalpha()` | `'A' <= c <= 'Z'` (after `.upper()`) |
| `str.isdigit()` | `'0' <= c <= '9'` |
| `bytes.hex()` | `" ".join("%02x" % b for b in data)` |

Especially dangerous in `boot.py` where `except Exception: pass` swallows the error silently.

### Barrel Imports

Keep `__init__.py` files minimal (no re-exports). If `__init__.py` imports a submodule, CircuitPython parses it eagerly — a single syntax error in any submodule prevents the whole package from importing.

---

## Hardware Reference

Hardware pin mappings are also documented in [docs/hardware-reference.md](../docs/hardware-reference.md).
For reverse engineering history, see [docs/midicaptain_reverse_engineering_handoff.md](../docs/midicaptain_reverse_engineering_handoff.md).

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
- 4 switch inputs: GP1, `board.LED` (GP25), GP9, GP10
- 2×2 grid layout: TL, TR, BL, BR
- ST7789 240×240 display
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
- Use `receiver_buffer_size=64`; wrap init in `try/except` — if UART unavailable, firmware must still boot (`midi_serial = None`)
- **Channel API gotcha**: `midi.send(ControlChange(cc, val, channel=X))` does **NOT** work — the library ignores `msg.channel`. Channel must be passed to `send()`: `midi.send(ControlChange(cc, val), channel=X)`. This caused issue #95 where all output was stuck on channel 1.
- **`in_channel`**: both USB and serial MIDI objects should use `in_channel=None` (receive all channels)
- Both `handle_midi()` reads USB and DIN ports; USB→DIN and DIN→USB forwarding happens there
- `_process_midi_msg` is source-agnostic; CC value >63 = ON, ≤63 = OFF. NoteOn/Off and PC are also handled.

### Device Auto-Detection

Two-tier detection (config first, then hardware probe):
1. **Config-based**: reads `"device"` field from `/config.json`
2. **Hardware probe fallback**: checks STD10-exclusive switch pins (GP0/GP18/GP19/GP20) — if 3+ read HIGH with pull-ups, it's STD10; otherwise Mini6. Cannot distinguish Mini6, NANO4, DUO2, or ONE1 by probe alone.

Always include `"device"` in `config.json` for NANO4, DUO2, and ONE1.

### Adding a New Device Variant — Checklist

When adding a new device, update ALL of these (copy-paste between variants is the #1 source of bugs):

1. `firmware/dev/devices/{device}.py` — pin definitions, LED count, `switch_to_led()`
2. `firmware/dev/config-{device}.json` — template config
3. `firmware/dev/code.py` — device detection allow-list + module import block
4. `firmware/dev/boot.py` — boot switch pin if different from GP1
5. `config-editor/src-tauri/src/config.rs` — `DeviceType` enum + button count match + validation
6. `config-editor/src-tauri/src/device.rs` — `is_midi_captain_config` + `parse_midi_captain_config` match arms
7. `config-editor/src/lib/types.ts` — `DeviceType` union
8. `config-editor/src/lib/formStore.ts` — all 4 device maps
9. `config-editor/src/lib/validation.ts` — device-specific constraints
10. `config-editor/src/lib/components/DeviceSection.svelte` — dropdown option + help text
11. `config-editor/src/lib/components/ButtonsSection.svelte` — `DEVICE_BUTTON_NAMES`
12. `tools/deploy.sh` — `VALID_DEVICES`, config scan loop, config selection, fallback deploy
13. `tools/deploy.ps1` — `ValidateSet`, config scan, config selection (must stay at parity with `.sh`)
14. `.github/workflows/ci.yml` — mpy-cross compilation loop
15. `docs/hardware-reference.md` — full hardware section
16. `AGENTS.md` (root) — device lists
17. Rust + `device.rs` tests — deserialization and `is_midi_captain_config` tests

**Tip:** `grep -r "duo2"` across the repo to catch any additional references.

### Reverse Engineering New Variants

See [docs/midicaptain_reverse_engineering_handoff.md](../docs/midicaptain_reverse_engineering_handoff.md) for the proven probe sequence. Scripts go in `firmware/dev/experiments/` and get deployed as `code.py` on the device.

---

## Firmware Patterns

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

All outgoing MIDI goes through `midi_send(msg)` which writes to both USB and 5-pin DIN simultaneously. Never call `midi.send()` directly — always use `midi_send()`.

`handle_midi()` is split into:
- `_process_midi_msg(msg, source)` — updates LED/button state from any received message (source-agnostic)
- `handle_midi()` — reads USB and DIN ports, calls `_process_midi_msg`, handles thru forwarding

### Button Dispatch (in `handle_switches`)

`dispatch_button(btn_num, pressed, btn_config, btn_state, channel)` branches on `message_type`:
- `"cc"` + toggle/momentary → sends CC with `cc_on`/`cc_off` values
- `"cc"` + select → calls `handle_cc_select_press`: sends `cc_on` (or `cc_off` on self-deselect), calls `update_select_group`
- `"note"` + toggle/momentary → sends NoteOn/NoteOff
- `"pc"` + pressed only → sends ProgramChange, calls `flash_pc_button`
- `"pc"` + select → calls `handle_pc_select_press`: sends PC, calls `update_select_group`
- `"pc_inc"` / `"pc_dec"` + pressed only → increments/decrements `pc_values[channel]`, sends PC, flashes
- `"hid"` + pressed only → calls `dispatch_hid(...)`, flashes LED

`pc_values` is a 16-element array (one per MIDI channel), shared across all pc_inc/dec buttons.

Keytimes: `btn_state.advance_keytime()` is called before reading `state_cfg`, so per-state overrides are applied from `btn_config["states"][keytime_index]` via `get_button_state_config()`.

### PC Button LED Modes

PC buttons support four LED modes (`mode` field); MIDI is always sent on press regardless:
- **`flash`** (default): brief LED pulse. Uses `flash_pc_button()` + `pc_flash_timers[]`. Duration configurable via `flash_ms` (default 200ms, range 50–5000).
- **`toggle`**: latching — `btn_state.state` flips on press, LED persists until next press.
- **`momentary`**: LED on while held, cleared on release.
- **`select`**: radio-group exclusivity (see Select Mode below).

Flash timers store **expiry time** as `time.monotonic() + flash_ms / 1000.0` (not loop-tick counting — the main loop has no sleep so tick count is unreliable).

### Select Mode (Radio Group)

Select-mode buttons enforce mutual exclusivity within a named group: pressing one activates it and deactivates all sibling buttons sharing the same `select_group`. Valid only on `pc` and `cc` types; multi-keytime configs are rejected by the validator (forced single-keytime). See [docs/plans/2026-05-07-issue-43-select-mode.md](../docs/plans/2026-05-07-issue-43-select-mode.md) and Issue #43.

**Config fields:**
- `mode: "select"` — opt in.
- `select_group: string` — required, non-empty. Buttons sharing this string form one radio group.
- `select_repress: "resend" | "nothing" | "deselect"` — what happens when re-pressing the already-active member. Default `"resend"`. `"deselect"` is CC-only in firmware (PC value is preserved at config level but no-oped, gated on #47).

**Helper:** `update_select_group(active_btn_num, group)` iterates `buttons`, sets `state` and LED for each member of the group (active button on, siblings off via each button's own `off_mode`). Writes only LEDs and `button_states` — never sends MIDI, so it's safe to call from RX paths without feedback risk.

**Press handlers:** `handle_pc_select_press` and `handle_cc_select_press` send the on-message and call `update_select_group`. Repress dispatches on `select_repress`. CC `deselect` sends `cc_off` and clears the active button without re-running group exclusivity (so the group is left with no active member).

**MIDI RX:** `_process_midi_msg` matches incoming PC by `(channel, program)` and CC by `(channel, cc, value == cc_on)` to a select-mode button and calls `update_select_group` (LED-only, no MIDI echo). `select_repress` is intentionally **not** consulted on RX — it governs local-press behavior only. RX is idempotent LED-and-state-only, which avoids feedback loops with hosts that echo their own messages.

**Deferred to #47** (multi-message-per-press): off-message on sibling deactivation; PC `deselect` repress firmware behavior.

**Future page handling:** when pages land, page-restore must repaint LEDs from `button_states[i].state` for select-mode buttons — do NOT reinit from config defaults, or latched group state is lost.

### HID Button Type

USB HID (keyboard + mouse) via the `"hid"` message type:

- `firmware/dev/core/hid.py`: `KEY_TABLE`, `MODIFIER_TABLE`, `dispatch_hid(keyboard, mouse, action, key, modifier, delay_ms)`
- Mouse button bitmasks (0x01, 0x02, 0x04) are **hardcoded** in `hid.py` — do not import from `adafruit_hid.mouse` in the hot dispatch path (CP 7.x does a filesystem scan per import call)
- HID is only enabled in `boot.py` if any button has `"type": "hid"` — keeps USB descriptor clean for MIDI-only setups

**HID config fields** (on ButtonConfig and StateOverride):
- `hid_action`: "send" | "press" | "release" | "delay" (default: "send")
- `hid_key`: OEM key name string, e.g. "A", "F1", "Space", "Mouse_L", "all"
- `hid_modifier`: "ctrl" | "shift" | "alt" | "option" | "windows" (optional)
- `hid_delay_ms`: 1-5000 ms (only used when action="delay")

### Config Loading (`firmware/dev/core/config.py`)

- `get_display_config(config)` — returns display settings with defaults (`"medium"` for all sizes)
- `get_usb_drive_name(config)` — validated USB volume label; defaults to `"MIDICAPTAIN"`
- `get_dev_mode(config)` — `bool(config.get("dev_mode", False))`, always safe to call
- `validate_usb_drive_name(name)` — enforces FAT32 label rules: uppercase, alphanumeric + underscore, max 11 chars
- `STATE_OVERRIDE_FIELDS` — fields that can be overridden per keytime state (see source for full list)
- Default button: `{"label": str(i+1), "cc": 20+i, "color": "white"}`

### USB Drive Behaviour (`boot.py`)

`storage.disable_usb_drive()` must be called **before** any `storage.remount()` call:

```python
dev_mode    = get_dev_mode(cfg)
switch_held = not switch_1.value   # GP1, pull-up: LOW = pressed
enable_usb_drive = dev_mode or switch_held

if not enable_usb_drive:
    storage.disable_usb_drive()    # MUST be first

if enable_usb_drive:
    storage.remount("/", readonly=False, label=usb_drive_name)
```

Two separate `if` blocks (not `if/else`) make the ordering constraint explicit — `disable` always appears above `remount`.

`boot.py` manually inserts `/core` via `sys.path.insert(0, "/core")` to import `config.py`. If config loading fails, a bare `except Exception` swallows it and safe defaults are used.

---

## Display & Fonts

**Display**: ST7789, 240×240px.

| File | Size | Used as |
|------|------|---------|
| `terminalio.FONT` (built-in) | ~8px | `"small"` |
| `PTSans-Regular-20.pcf` | 20px | `"medium"` |
| `PTSans-Bold-60.pcf` | 60px | `"large"` |
| `PTSans-NarrowBold-54.pcf` | 54px | unused — candidate for future use |

**Font overflow**: The `"large"` font (60px bold) overflows the status line for strings longer than ~5 chars. A dynamic font-switching approach (fall back to medium when text exceeds `DISPLAY_WIDTH - 4`) is the proper fix — pending completion in `set_status_text()`.

---

## Testing (Firmware)

### On-Device Testing
- Copy code to MIDICAPTAIN volume, observe behavior via serial console
- Use `screen` with auto-reconnect loop. See `docs/screen-cheatsheet.md` for usage tips.
- Experiments in `firmware/dev/experiments/` for isolated testing

### USB Drive / Boot Mode Hardware Tests
When changing `boot.py`, `usb_drive_name`, or `dev_mode`, verify on physical hardware:
1. **Performance mode** (default): power on without Switch 1 → no USB drive appears
2. **Update mode**: hold Switch 1 while powering on → drive mounts with configured name
3. **Dev mode** (`dev_mode: true`): drive always mounts on boot without switch press
4. **Custom name**: set `usb_drive_name`, power-cycle with Switch 1 → drive appears with that name
5. **Validation**: lowercase, special chars, >11 chars → verify auto-correction or fallback to `"MIDICAPTAIN"`
6. **Config failure**: corrupt `config.json` → device still boots, falls back to `"MIDICAPTAIN"`

### Desktop Tests (pytest)
- `tests/` with CircuitPython hardware mocks in `tests/mocks/`
- Run: `python3 -m pytest tests/` from repo root
- See `tests/AGENTS.md` (if present) or root `AGENTS.md` for full suite details
