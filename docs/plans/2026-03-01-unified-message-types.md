# Unified MIDI Message Types Implementation Plan

**Status:** Shipped — unified message `type`s are in the current config schema.
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Note and PC (Program Change) message type support to both firmware and GUI config editor, unified with the existing CC type and keytimes system from PR #50.

**Architecture:** Add a `type` field (`cc` | `note` | `pc` | `pc_inc` | `pc_dec`) to button configs. Each type gets its own set of validated fields in `config.py`. `code.py` dispatches on `type` when sending/receiving MIDI. The GUI config editor shows only the relevant input fields for the selected type.

**Tech Stack:** CircuitPython firmware (Python), pytest for firmware tests, SvelteKit + TypeScript for config editor (no editor test runner — manual review only).

**Backward compatibility:** Any button without a `type` field defaults to `cc`. Invalid types fall back to `cc`.

---

## Current State (after PR #50 merge)

- `firmware/dev/core/config.py`: Has keytimes support; CC-only type system (no `type` field)
- `firmware/dev/code.py`: Has keytimes/ButtonState; CC-only MIDI dispatch
- `config-editor/src/lib/types.ts`: `ButtonConfig` is CC-only
- `config-editor/src/lib/validation.ts`: Validates CC fields only
- `config-editor/src/lib/components/ButtonRow.svelte`: Shows CC fields only
- Tests: 81 passing

---

## Task 1: Add `type` field to firmware `config.py`

**Files:**
- Modify: `firmware/dev/core/config.py`
- Test: `tests/test_config.py`

### Step 1: Write failing tests

Add to `tests/test_config.py` after the existing `TestValidateButton` class:

```python
class TestButtonMessageTypes:
    """Tests for multi-type button message support."""

    def test_default_type_is_cc(self):
        btn = validate_button({}, index=0)
        assert btn["type"] == "cc"

    def test_cc_type_explicit(self):
        btn = validate_button({"type": "cc", "cc": 50}, index=0)
        assert btn["type"] == "cc"
        assert btn["cc"] == 50
        assert btn["cc_on"] == 127
        assert btn["cc_off"] == 0

    def test_cc_type_no_note_fields(self):
        btn = validate_button({"type": "cc"}, index=0)
        assert "note" not in btn
        assert "velocity_on" not in btn
        assert "velocity_off" not in btn

    def test_cc_type_no_pc_fields(self):
        btn = validate_button({"type": "cc"}, index=0)
        assert "program" not in btn
        assert "pc_step" not in btn

    def test_note_type(self):
        btn = validate_button({"type": "note", "note": 60}, index=0)
        assert btn["type"] == "note"
        assert btn["note"] == 60
        assert btn["velocity_on"] == 127
        assert btn["velocity_off"] == 0

    def test_note_type_defaults(self):
        btn = validate_button({"type": "note"}, index=0)
        assert btn["note"] == 60
        assert btn["velocity_on"] == 127
        assert btn["velocity_off"] == 0

    def test_note_type_custom_velocity(self):
        btn = validate_button({"type": "note", "note": 36, "velocity_on": 100, "velocity_off": 0}, index=0)
        assert btn["velocity_on"] == 100
        assert btn["velocity_off"] == 0

    def test_note_type_no_cc_fields(self):
        btn = validate_button({"type": "note"}, index=0)
        assert "cc" not in btn
        assert "cc_on" not in btn
        assert "cc_off" not in btn

    def test_pc_type(self):
        btn = validate_button({"type": "pc", "program": 5}, index=0)
        assert btn["type"] == "pc"
        assert btn["program"] == 5

    def test_pc_type_default_program(self):
        btn = validate_button({"type": "pc"}, index=0)
        assert btn["program"] == 0

    def test_pc_type_no_cc_fields(self):
        btn = validate_button({"type": "pc"}, index=0)
        assert "cc" not in btn
        assert "cc_on" not in btn
        assert "cc_off" not in btn

    def test_pc_inc_type(self):
        btn = validate_button({"type": "pc_inc", "pc_step": 5}, index=0)
        assert btn["type"] == "pc_inc"
        assert btn["pc_step"] == 5

    def test_pc_dec_type(self):
        btn = validate_button({"type": "pc_dec", "pc_step": 2}, index=0)
        assert btn["type"] == "pc_dec"
        assert btn["pc_step"] == 2

    def test_pc_inc_dec_default_step(self):
        btn_inc = validate_button({"type": "pc_inc"}, index=0)
        btn_dec = validate_button({"type": "pc_dec"}, index=0)
        assert btn_inc["pc_step"] == 1
        assert btn_dec["pc_step"] == 1

    def test_invalid_type_falls_back_to_cc(self):
        btn = validate_button({"type": "invalid_type"}, index=0)
        assert btn["type"] == "cc"
        assert "cc" in btn

    def test_type_inherits_global_channel(self):
        btn = validate_button({"type": "note", "note": 48}, index=0, global_channel=3)
        assert btn["channel"] == 3

    def test_keytimes_works_with_note_type(self):
        btn = validate_button({"type": "note", "note": 60, "keytimes": 2}, index=0)
        assert btn["keytimes"] == 2

    def test_keytimes_works_with_cc_type(self):
        btn = validate_button({"type": "cc", "cc": 20, "keytimes": 3}, index=0)
        assert btn["keytimes"] == 3
```

### Step 2: Run tests to verify they fail

```bash
python3 -m pytest tests/test_config.py::TestButtonMessageTypes -v
```

Expected: All new tests FAIL (no `type` field exists yet)

### Step 3: Implement type support in `config.py`

Replace the `validate_button` function body. The new implementation:

```python
VALID_TYPES = ("cc", "note", "pc", "pc_inc", "pc_dec")

def validate_button(btn, index=0, global_channel=None):
    """Validate a button config dict, filling in defaults.

    Args:
        btn: Button config dict
        index: Button index (for default CC calculation)
        global_channel: Global MIDI channel (0-15), used if button doesn't specify channel

    Returns:
        Validated button config with all required fields

    Button Types:
        - "cc": Control Change (default)
        - "note": MIDI Note On/Off
        - "pc": Program Change fixed
        - "pc_inc": Program Change increment
        - "pc_dec": Program Change decrement
    """
    if global_channel is not None:
        default_channel = global_channel
    else:
        default_channel = 0

    # Keytimes: default to 1 (no cycling), clamp to 1-99
    keytimes = btn.get("keytimes", 1)
    if not isinstance(keytimes, int):
        keytimes = 1
    keytimes = max(1, min(99, keytimes))

    # Determine message type, fall back to cc if invalid
    msg_type = btn.get("type", "cc")
    if msg_type not in VALID_TYPES:
        msg_type = "cc"

    validated = {
        "label": btn.get("label", str(index + 1)),
        "color": btn.get("color", "white"),
        "mode": btn.get("mode", "toggle"),
        "off_mode": btn.get("off_mode", "dim"),
        "channel": btn.get("channel", default_channel),
        "type": msg_type,
        "keytimes": keytimes,
    }

    # Type-specific fields
    if msg_type == "cc":
        validated["cc"] = btn.get("cc", 20 + index)
        validated["cc_on"] = btn.get("cc_on", 127)
        validated["cc_off"] = btn.get("cc_off", 0)
    elif msg_type == "note":
        validated["note"] = btn.get("note", 60)
        validated["velocity_on"] = btn.get("velocity_on", 127)
        validated["velocity_off"] = btn.get("velocity_off", 0)
    elif msg_type == "pc":
        validated["program"] = btn.get("program", 0)
    elif msg_type in ("pc_inc", "pc_dec"):
        validated["pc_step"] = btn.get("pc_step", 1)

    # For keytimes > 1, validate and pass through states array
    if keytimes > 1:
        states = btn.get("states", [])
        if isinstance(states, list):
            validated_states = []
            for state in states:
                if isinstance(state, dict):
                    validated_state = {}
                    for field in ("cc", "cc_on", "cc_off", "note", "velocity_on", "velocity_off", "color", "label"):
                        if field in state:
                            validated_state[field] = state[field]
                    validated_states.append(validated_state)
            if validated_states:
                validated["states"] = validated_states

    return validated
```

Note: Add `VALID_TYPES` constant at module level (top of file, after imports).

### Step 4: Run tests to verify they pass

```bash
python3 -m pytest tests/test_config.py -v
```

Expected: All 81 + new tests PASS

### Step 5: Commit

```bash
git add firmware/dev/core/config.py tests/test_config.py
git commit -m "Add multi-type button support to config.py: cc, note, pc, pc_inc, pc_dec"
```

---

## Task 2: Add MIDI stubs to conftest and note/PC tests for code.py

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_config.py` (verify existing cc defaults still pass)

### Step 1: Add MIDI stubs to `conftest.py`

In `install_mocks()`, after `sys.modules["adafruit_midi.control_change"] = StubModule()`, add:

```python
sys.modules["adafruit_midi.program_change"] = StubModule()
sys.modules["adafruit_midi.note_on"] = StubModule()
sys.modules["adafruit_midi.note_off"] = StubModule()
```

### Step 2: Run full test suite to confirm still passing

```bash
python3 -m pytest tests/ -q
```

Expected: All tests PASS (no regressions)

### Step 3: Commit

```bash
git add tests/conftest.py
git commit -m "Add MIDI stub modules for program_change, note_on, note_off"
```

---

## Task 3: Extend `code.py` with Note and PC message dispatch

**Files:**
- Modify: `firmware/dev/code.py`

This file runs on CircuitPython hardware and can't be fully unit-tested, but the changes follow the exact same patterns already used for CC.

### Step 1: Add imports (near line 37, after existing ControlChange import)

```python
from adafruit_midi.program_change import ProgramChange
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
```

### Step 2: Add PC state arrays (near line 378, after existing `button_states`)

```python
pc_values = [0] * BUTTON_COUNT       # Current PC value for each button (0-127)
pc_flash_timers = [0] * BUTTON_COUNT # Countdown for PC button LED flash
PC_FLASH_DURATION = 10               # ~100ms at typical loop speed (~10ms/iter)
```

### Step 3: Add PC helper functions (after `init_leds`, before "Polling Functions" section)

```python
def clamp_pc_value(value):
    """Clamp PC value to valid MIDI range (0-127)."""
    return max(0, min(127, value))


def flash_pc_button(button_idx):
    """Light LED briefly for PC button press feedback.

    Args:
        button_idx: 1-indexed button number (matches set_button_state convention)
    """
    set_button_state(button_idx, True)
    pc_flash_timers[button_idx - 1] = PC_FLASH_DURATION


def update_pc_flash_timers():
    """Decrement flash timers and turn off LEDs when expired. Call each main loop."""
    for i in range(BUTTON_COUNT):
        if pc_flash_timers[i] > 0:
            pc_flash_timers[i] -= 1
            if pc_flash_timers[i] == 0:
                set_button_state(i + 1, False)
```

### Step 4: Extend `handle_midi()` to handle NoteOn, NoteOff, ProgramChange

Replace the existing `handle_midi` function body. The new version handles all incoming message types:

```python
def handle_midi():
    """Handle incoming MIDI messages."""
    msg = midi.receive()
    if not msg:
        return

    msg_channel = getattr(msg, 'channel', 0) or 0

    if isinstance(msg, ControlChange):
        cc = msg.control
        val = msg.value
        print(f"[MIDI RX] Ch{msg_channel+1} CC{cc}={val}")
        for i, btn_config in enumerate(buttons):
            if btn_config.get("type", "cc") == "cc" and btn_config.get("cc") == cc and btn_config.get("channel", 0) == msg_channel:
                set_button_state(i + 1, val > 63)
                status_label.text = f"RX CC{cc}={val}"
                break

    elif isinstance(msg, NoteOn):
        note = msg.note
        vel = msg.velocity
        print(f"[MIDI RX] Ch{msg_channel+1} NoteOn{note} vel{vel}")
        for i, btn_config in enumerate(buttons):
            if btn_config.get("type") == "note" and btn_config.get("note") == note and btn_config.get("channel", 0) == msg_channel:
                set_button_state(i + 1, vel > 0)
                status_label.text = f"RX Note{note}"
                break

    elif isinstance(msg, NoteOff):
        note = msg.note
        print(f"[MIDI RX] Ch{msg_channel+1} NoteOff{note}")
        for i, btn_config in enumerate(buttons):
            if btn_config.get("type") == "note" and btn_config.get("note") == note and btn_config.get("channel", 0) == msg_channel:
                set_button_state(i + 1, False)
                status_label.text = f"RX NoteOff{note}"
                break

    elif isinstance(msg, ProgramChange):
        program = msg.patch
        print(f"[MIDI RX] Ch{msg_channel+1} PC{program}")
        for i, btn_config in enumerate(buttons):
            if btn_config.get("type") in ("pc_inc", "pc_dec") and btn_config.get("channel", 0) == msg_channel:
                pc_values[i] = program
        status_label.text = f"RX PC{program}"
```

### Step 5: Extend `handle_switches()` to dispatch all 5 message types

Replace the inner `if/elif pressed` block with a full type-dispatch. Find the block starting around line 631:

```python
            message_type = btn_config.get("type", "cc")
            mode = btn_config.get("mode", "toggle")
            channel = btn_config.get("channel", 0)

            if message_type == "cc":
                cc = btn_config.get("cc", 20 + idx)
                cc_on = btn_config.get("cc_on", 127)
                cc_off = btn_config.get("cc_off", 0)
                if mode == "momentary":
                    val = cc_on if pressed else cc_off
                    set_button_state(btn_num, pressed)
                    midi.send(ControlChange(cc, val, channel=channel))
                    print(f"[MIDI TX] Ch{channel+1} CC{cc}={val} (switch {btn_num}, momentary)")
                    status_label.text = f"TX CC{cc}={val}"
                elif pressed:
                    new_state = not button_states[idx]
                    set_button_state(btn_num, new_state)
                    val = cc_on if new_state else cc_off
                    midi.send(ControlChange(cc, val, channel=channel))
                    print(f"[MIDI TX] Ch{channel+1} CC{cc}={val} (switch {btn_num}, toggle)")
                    status_label.text = f"TX CC{cc}={'ON' if new_state else 'OFF'}"

            elif message_type == "note":
                note = btn_config.get("note", 60)
                vel_on = btn_config.get("velocity_on", 127)
                vel_off = btn_config.get("velocity_off", 0)
                if mode == "momentary":
                    if pressed:
                        midi.send(NoteOn(note, vel_on, channel=channel))
                        set_button_state(btn_num, True)
                        print(f"[MIDI TX] Ch{channel+1} NoteOn{note} vel{vel_on} (switch {btn_num})")
                        status_label.text = f"TX Note{note}"
                    else:
                        midi.send(NoteOff(note, vel_off, channel=channel))
                        set_button_state(btn_num, False)
                        print(f"[MIDI TX] Ch{channel+1} NoteOff{note} (switch {btn_num})")
                elif pressed:
                    new_state = not button_states[idx]
                    set_button_state(btn_num, new_state)
                    if new_state:
                        midi.send(NoteOn(note, vel_on, channel=channel))
                        print(f"[MIDI TX] Ch{channel+1} NoteOn{note} vel{vel_on} (switch {btn_num}, toggle on)")
                        status_label.text = f"TX Note{note} ON"
                    else:
                        midi.send(NoteOff(note, vel_off, channel=channel))
                        print(f"[MIDI TX] Ch{channel+1} NoteOff{note} (switch {btn_num}, toggle off)")
                        status_label.text = f"TX Note{note} OFF"

            elif message_type == "pc" and pressed:
                program = btn_config.get("program", 0)
                midi.send(ProgramChange(program, channel=channel))
                print(f"[MIDI TX] Ch{channel+1} PC{program} (switch {btn_num})")
                status_label.text = f"TX PC{program}"
                flash_pc_button(btn_num)

            elif message_type == "pc_inc" and pressed:
                step = btn_config.get("pc_step", 1)
                pc_values[idx] = clamp_pc_value(pc_values[idx] + step)
                midi.send(ProgramChange(pc_values[idx], channel=channel))
                print(f"[MIDI TX] Ch{channel+1} PC{pc_values[idx]} (switch {btn_num}, inc)")
                status_label.text = f"TX PC{pc_values[idx]}"
                flash_pc_button(btn_num)

            elif message_type == "pc_dec" and pressed:
                step = btn_config.get("pc_step", 1)
                pc_values[idx] = clamp_pc_value(pc_values[idx] - step)
                midi.send(ProgramChange(pc_values[idx], channel=channel))
                print(f"[MIDI TX] Ch{channel+1} PC{pc_values[idx]} (switch {btn_num}, dec)")
                status_label.text = f"TX PC{pc_values[idx]}"
                flash_pc_button(btn_num)
```

### Step 6: Add `update_pc_flash_timers()` to main loop

In the `while True:` loop (near bottom of file), after `handle_switches()`:

```python
    update_pc_flash_timers()
```

### Step 7: Run full test suite to confirm no regressions

```bash
python3 -m pytest tests/ -q
```

Expected: All tests PASS (code.py changes can't be directly tested here but must not break imports)

### Step 8: Commit

```bash
git add firmware/dev/code.py
git commit -m "Add Note and PC message dispatch in code.py: 5 message types fully supported"
```

---

## Task 4: Add example config showing all 5 types

**Files:**
- Create: `firmware/dev/config-example-all-types.json`

### Step 1: Create the example config

```json
{
  "device": "std10",
  "display": {
    "button_text_size": "medium",
    "status_text_size": "medium",
    "expression_text_size": "medium"
  },
  "buttons": [
    {"label": "CC20",   "type": "cc",     "cc": 20,      "color": "red"},
    {"label": "TREM",   "type": "note",   "note": 60,    "velocity_on": 127, "velocity_off": 0, "color": "blue", "mode": "momentary"},
    {"label": "CHORD",  "type": "note",   "note": 48,    "color": "cyan", "mode": "toggle"},
    {"label": "PATCH1", "type": "pc",     "program": 0,  "color": "green"},
    {"label": "PATCH2", "type": "pc",     "program": 1,  "color": "yellow"},
    {"label": "PATCH3", "type": "pc",     "program": 2,  "color": "magenta"},
    {"label": "PATCH4", "type": "pc",     "program": 3,  "color": "white"},
    {"label": "PATCH5", "type": "pc",     "program": 4,  "color": "orange"},
    {"label": "PC+",    "type": "pc_inc", "pc_step": 1,  "color": "orange"},
    {"label": "PC-",    "type": "pc_dec", "pc_step": 1,  "color": "purple"}
  ],
  "encoder": {
    "enabled": true,
    "cc": 11,
    "label": "ENC",
    "min": 0,
    "max": 127,
    "initial": 64,
    "steps": null,
    "push": {
      "enabled": true,
      "cc": 14,
      "label": "PUSH",
      "mode": "momentary"
    }
  }
}
```

### Step 2: Commit

```bash
git add firmware/dev/config-example-all-types.json
git commit -m "Add example config showing all 5 message types"
```

---

## Task 5: Update TypeScript types in config editor

**Files:**
- Modify: `config-editor/src/lib/types.ts`

### Step 1: Update `types.ts`

Add `MessageType` and update `ButtonConfig`:

```typescript
export type MessageType = 'cc' | 'note' | 'pc' | 'pc_inc' | 'pc_dec';
```

Update `ButtonConfig` interface — replace the current CC-only interface with:

```typescript
export interface ButtonConfig {
  label: string;
  color: ButtonColor;
  type?: MessageType;      // defaults to 'cc'
  mode?: ButtonMode;
  off_mode?: OffMode;
  channel?: number;        // Stored as 0-15, displayed as 1-16
  // CC fields (type='cc')
  cc?: number;
  cc_on?: number;          // CC value when ON (default: 127)
  cc_off?: number;         // CC value when OFF (default: 0)
  // Note fields (type='note')
  note?: number;           // MIDI note number 0-127
  velocity_on?: number;    // Note velocity when ON (default: 127)
  velocity_off?: number;   // Note velocity when OFF (default: 0)
  // PC fields (type='pc')
  program?: number;        // Program number 0-127
  // PC inc/dec fields (type='pc_inc' | 'pc_dec')
  pc_step?: number;        // Step size (default: 1)
}
```

Note: `cc` becomes optional since Note/PC buttons don't have a CC number. Existing configs that don't include `type` still work — the GUI and firmware both default to `cc`.

### Step 2: Commit

```bash
git add config-editor/src/lib/types.ts
git commit -m "Add MessageType and type-specific fields to ButtonConfig TypeScript types"
```

---

## Task 6: Update validation in config editor

**Files:**
- Modify: `config-editor/src/lib/validation.ts`

### Step 1: Add new validators and update `validateConfig`

Add `note` and `velocity` validators after the existing `cc` validator:

```typescript
  note: (value: number): string | null => {
    if (value === undefined || value === null) return 'Note is required';
    if (value < 0 || value > 127) return 'Note must be between 0 and 127';
    if (!Number.isInteger(value)) return 'Note must be an integer';
    return null;
  },

  velocity: (value: number): string | null => {
    if (value < 0 || value > 127) return 'Velocity must be between 0 and 127';
    if (!Number.isInteger(value)) return 'Velocity must be an integer';
    return null;
  },

  program: (value: number): string | null => {
    if (value === undefined || value === null) return 'Program is required';
    if (value < 0 || value > 127) return 'Program must be between 0 and 127';
    if (!Number.isInteger(value)) return 'Program must be an integer';
    return null;
  },

  pcStep: (value: number): string | null => {
    if (value < 1 || value > 127) return 'Step must be between 1 and 127';
    if (!Number.isInteger(value)) return 'Step must be an integer';
    return null;
  },
```

Replace the button validation loop in `validateConfig` with type-aware validation:

```typescript
  config.buttons.forEach((btn, idx) => {
    const labelError = validators.label(btn.label);
    if (labelError) errors.set(`buttons[${idx}].label`, labelError);

    const msgType = btn.type ?? 'cc';

    if (msgType === 'cc') {
      if (btn.cc !== undefined) {
        const ccError = validators.cc(btn.cc);
        if (ccError) errors.set(`buttons[${idx}].cc`, ccError);
      }
    } else if (msgType === 'note') {
      if (btn.note !== undefined) {
        const noteError = validators.note(btn.note);
        if (noteError) errors.set(`buttons[${idx}].note`, noteError);
      }
      if (btn.velocity_on !== undefined) {
        const velError = validators.velocity(btn.velocity_on);
        if (velError) errors.set(`buttons[${idx}].velocity_on`, velError);
      }
      if (btn.velocity_off !== undefined) {
        const velError = validators.velocity(btn.velocity_off);
        if (velError) errors.set(`buttons[${idx}].velocity_off`, velError);
      }
    } else if (msgType === 'pc') {
      if (btn.program !== undefined) {
        const progError = validators.program(btn.program);
        if (progError) errors.set(`buttons[${idx}].program`, progError);
      }
    } else if (msgType === 'pc_inc' || msgType === 'pc_dec') {
      if (btn.pc_step !== undefined) {
        const stepError = validators.pcStep(btn.pc_step);
        if (stepError) errors.set(`buttons[${idx}].pc_step`, stepError);
      }
    }
  });
```

### Step 2: Commit

```bash
git add config-editor/src/lib/validation.ts
git commit -m "Add type-aware validation for note, pc, pc_inc, pc_dec message types"
```

---

## Task 7: Update GUI `ButtonRow.svelte` with type selector and conditional fields

**Files:**
- Modify: `config-editor/src/lib/components/ButtonRow.svelte`

### Step 1: Update the `<script>` block

Replace the import line and add new handlers and derived values:

```typescript
import type { ButtonConfig, ButtonColor, ButtonMode, OffMode, MessageType } from '$lib/types';
```

Add derived type check after `const basePath`:
```typescript
let msgType = $derived((button.type ?? 'cc') as MessageType);
let isCC = $derived(msgType === 'cc');
let isNote = $derived(msgType === 'note');
let isPC = $derived(msgType === 'pc');
let isPCIncDec = $derived(msgType === 'pc_inc' || msgType === 'pc_dec');
let showMode = $derived(isCC || isNote);  // PC types are always press-only
```

Add new handler functions after existing ones:

```typescript
function handleTypeChange(e: Event) {
  const target = e.target as HTMLSelectElement;
  onUpdate('type', target.value as MessageType);
}

function handleNoteChange(e: Event) {
  const target = e.target as HTMLInputElement;
  onUpdate('note', parseInt(target.value));
}

function handleVelocityOnChange(e: Event) {
  const target = e.target as HTMLInputElement;
  const value = target.value === '' ? undefined : parseInt(target.value);
  onUpdate('velocity_on', value);
}

function handleVelocityOffChange(e: Event) {
  const target = e.target as HTMLInputElement;
  const value = target.value === '' ? undefined : parseInt(target.value);
  onUpdate('velocity_off', value);
}

function handleProgramChange(e: Event) {
  const target = e.target as HTMLInputElement;
  onUpdate('program', parseInt(target.value));
}

function handlePCStepChange(e: Event) {
  const target = e.target as HTMLInputElement;
  onUpdate('pc_step', parseInt(target.value));
}
```

Add new error bindings after existing ones:
```typescript
let noteError = $derived($validationErrors.get(`${basePath}.note`));
let velocityOnError = $derived($validationErrors.get(`${basePath}.velocity_on`));
let velocityOffError = $derived($validationErrors.get(`${basePath}.velocity_off`));
let programError = $derived($validationErrors.get(`${basePath}.program`));
let pcStepError = $derived($validationErrors.get(`${basePath}.pc_step`));
```

### Step 2: Update the template HTML

After the Label field and before the Channel field, add the Type selector:

```html
<div class="field">
  <label class="field-label">Type:</label>
  <select
    class="select"
    value={button.type ?? 'cc'}
    onchange={handleTypeChange}
    disabled={disabled}
  >
    <option value="cc">CC</option>
    <option value="note">Note</option>
    <option value="pc">PC Fixed</option>
    <option value="pc_inc">PC+</option>
    <option value="pc_dec">PC-</option>
  </select>
</div>
```

Replace the CC field block with a conditional section:

```html
{#if isCC}
  <div class="field">
    <label class="field-label">CC:</label>
    <input type="number" class="input-cc" class:error={!!ccError}
      value={button.cc ?? ''} onblur={handleCCChange} disabled={disabled}
      min="0" max="127" />
    {#if ccError}<span class="error-text">{ccError}</span>{/if}
  </div>
  <div class="field">
    <label class="field-label">ON Value:</label>
    <input type="number" class="input-cc-value" class:error={!!ccOnError}
      value={button.cc_on !== undefined ? button.cc_on : ''} onblur={handleCCOnChange}
      disabled={disabled} min="0" max="127" placeholder="127" />
    {#if ccOnError}<span class="error-text">{ccOnError}</span>{/if}
  </div>
  <div class="field">
    <label class="field-label">OFF Value:</label>
    <input type="number" class="input-cc-value" class:error={!!ccOffError}
      value={button.cc_off !== undefined ? button.cc_off : ''} onblur={handleCCOffChange}
      disabled={disabled} min="0" max="127" placeholder="0" />
    {#if ccOffError}<span class="error-text">{ccOffError}</span>{/if}
  </div>
{:else if isNote}
  <div class="field">
    <label class="field-label">Note:</label>
    <input type="number" class="input-cc" class:error={!!noteError}
      value={button.note ?? 60} onblur={handleNoteChange} disabled={disabled}
      min="0" max="127" />
    {#if noteError}<span class="error-text">{noteError}</span>{/if}
  </div>
  <div class="field">
    <label class="field-label">Vel ON:</label>
    <input type="number" class="input-cc-value" class:error={!!velocityOnError}
      value={button.velocity_on !== undefined ? button.velocity_on : ''} onblur={handleVelocityOnChange}
      disabled={disabled} min="0" max="127" placeholder="127" />
    {#if velocityOnError}<span class="error-text">{velocityOnError}</span>{/if}
  </div>
  <div class="field">
    <label class="field-label">Vel OFF:</label>
    <input type="number" class="input-cc-value" class:error={!!velocityOffError}
      value={button.velocity_off !== undefined ? button.velocity_off : ''} onblur={handleVelocityOffChange}
      disabled={disabled} min="0" max="127" placeholder="0" />
    {#if velocityOffError}<span class="error-text">{velocityOffError}</span>{/if}
  </div>
{:else if isPC}
  <div class="field">
    <label class="field-label">Program:</label>
    <input type="number" class="input-cc" class:error={!!programError}
      value={button.program ?? 0} onblur={handleProgramChange} disabled={disabled}
      min="0" max="127" />
    {#if programError}<span class="error-text">{programError}</span>{/if}
  </div>
{:else if isPCIncDec}
  <div class="field">
    <label class="field-label">Step:</label>
    <input type="number" class="input-cc" class:error={!!pcStepError}
      value={button.pc_step ?? 1} onblur={handlePCStepChange} disabled={disabled}
      min="1" max="127" />
    {#if pcStepError}<span class="error-text">{pcStepError}</span>{/if}
  </div>
{/if}
```

Replace the Switch Mode and LED Off Mode fields to be conditional on type (PC types don't use them):

```html
{#if showMode}
  <div class="field">
    <label class="field-label">Switch Mode:</label>
    <select class="select" value={button.mode || 'toggle'} onchange={handleModeChange} disabled={disabled}>
      <option value="toggle">Toggle</option>
      <option value="momentary">Momentary</option>
    </select>
  </div>
  <div class="field">
    <label class="field-label">LED Off Mode:</label>
    <select class="select" value={button.off_mode || 'dim'} onchange={handleOffModeChange} disabled={disabled}>
      <option value="dim">Dim</option>
      <option value="off">Off</option>
    </select>
  </div>
{/if}
```

### Step 3: Verify in browser (manual)

Run the config editor dev server and verify:
- Type dropdown shows all 5 options
- Selecting CC shows CC/ON/OFF fields and Switch Mode/LED Off Mode
- Selecting Note shows Note/Vel ON/Vel OFF and Switch Mode/LED Off Mode
- Selecting PC Fixed shows Program field only (no mode)
- Selecting PC+/PC- shows Step field only (no mode)
- Existing configs without `type` field load correctly as CC

```bash
cd config-editor && npm run dev
```

### Step 4: Commit

```bash
git add config-editor/src/lib/components/ButtonRow.svelte
git commit -m "Update ButtonRow GUI: type selector with conditional fields for all 5 message types"
```

---

## Task 8: Update `formStore.ts` to handle type changes cleanly

**Files:**
- Modify: `config-editor/src/lib/formStore.ts`

When a user changes a button's `type`, the old type's fields remain in the config object. This is mostly harmless (firmware ignores extra fields), but check if `formStore.ts` needs any handling.

### Step 1: Read the current formStore

```bash
# Read the file first
cat config-editor/src/lib/formStore.ts
```

### Step 2: Check if `updateButtonField` needs any changes

If `updateButtonField` simply does `button[field] = value`, no changes are needed — the firmware's `validate_button` already strips out irrelevant fields server-side when loading. The GUI just passes through what it has.

If there's any logic that assumes `cc` is always present, update it to handle optional `cc`.

### Step 3: Commit if changes were needed

```bash
git add config-editor/src/lib/formStore.ts
git commit -m "Handle optional cc field in formStore for multi-type buttons"
```

---

## Task 9: Final integration check

### Step 1: Run all firmware tests

```bash
python3 -m pytest tests/ -v
```

Expected: All tests PASS

### Step 2: Manual check — load example config in GUI

1. Start dev server: `cd config-editor && npm run dev`
2. Load `firmware/dev/config-example-all-types.json`
3. Verify all 10 buttons display correctly with correct field types
4. Change a button type and verify fields update

### Step 3: Final commit if any cleanup needed, then summary

```bash
git log --oneline -10
```

Verify clean commit history with each feature isolated.
