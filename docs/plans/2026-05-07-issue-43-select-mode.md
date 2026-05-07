# Plan: SELECT mode (Issue #43)

**Status:** Design locked, ready to implement
**Issue:** https://github.com/MC-Music-Workshop/midi-captain-max/issues/43
**Author:** Design hashed out 2026-05-06 / 07. Plan written for execution by another model.

---

## What this is

Add a `select` (radio-group) mode to PC and CC buttons. Pressing one select-mode button activates it (sends MIDI, lights LED), and deactivates all sibling buttons sharing the same `select_group` (LED off, no MIDI emitted). Incoming MIDI that matches a select-mode button's listening config produces the same effect.

## Critical: read before starting

- This plan is the **single source of truth** for V1 scope. Do not add features beyond what's listed here even if they seem useful — explicit out-of-scope items are at the bottom.
- Follow TDD for step 1 (validator). Write failing tests, then implement, then make tests pass.
- All design decisions have been made. Do not re-litigate. If something genuinely seems wrong, stop and ask the user before improvising.
- Do **not** run `deploy.sh`, `git checkout`, or `git pull` on the user's behalf.
- Use colons not em-dashes in bold-label lists in any docs you write.
- After implementation, request code review (use the `requesting-code-review` skill) before opening a PR.

---

## Design summary

### Schema fields (added to button objects)

| Field | Type | When required | Default | Notes |
|---|---|---|---|---|
| `mode` | enum | extends existing enum | (existing per-type defaults) | Adds `"select"` to `flash`/`toggle`/`momentary`. |
| `select_group` | string | required + non-empty when `mode == "select"` | n/a | Hard-rejected if missing/empty. |
| `select_repress` | enum | optional when `mode == "select"` | `"resend"` | Values: `"resend"`, `"nothing"`, `"deselect"`. |

### Where it applies

`mode == "select"` is **valid only on `pc` and `cc` button types**. Validator rejects it on `pc_inc`, `pc_dec`, `note`, `hid`. Multi-keytime configs (more than one keytime defined) with `mode == "select"` are also rejected.

### Behavior

**Press a select-mode button:**
1. Send the on-message (PC: `program`; CC: `cc_on`).
2. Latch its LED on.
3. Iterate all buttons; for each select-mode member with the same `select_group`, set its state to `(i+1 == active_btn_num)` — i.e. set this button on, all siblings off. Each sibling LED uses its own configured `off_mode` (`dim` or `off`).

**Press the already-active member:**
- `"resend"` (default): re-emit on-message. LED stays on.
- `"nothing"`: no MIDI sent. LED stays on.
- `"deselect"`:
    - **CC:** send `cc_off`, LED off, group has no active member.
    - **PC:** preserved in config but **firmware no-ops** (treats as `resend`). Editor disables the option with help-text. Will be activated when #47 ships.

**MIDI RX:** when an incoming PC or CC matches a select-mode button's listening config (channel + program for PC; channel + cc number + value equals `cc_on` for CC), route through the **same code path as a local press**. Same semantics, same `select_repress` handling for repeated incoming activations.

**Boot:** all select-mode LEDs come up off. No persistence.

**No infinite-loop risk:** `update_select_group` only writes LEDs and `button_states`; never sends MIDI. RX → helper is idempotent.

---

## Wire-in points (verified, but verify line numbers haven't drifted)

| File | Line(s) | Purpose |
|---|---|---|
| `config.schema.json` | 58–61 | `ButtonMode` enum |
| `firmware/dev/core/config.py` | 104–108 | mode validator |
| `firmware/dev/core/config.py` | 135–138 | per-type field persistence (mirror for new fields) |
| `firmware/dev/code.py` | 748–756 | `flash_pc_button` (new helper goes nearby) |
| `firmware/dev/code.py` | 790–820 | `_process_midi_msg` RX handler |
| `firmware/dev/code.py` | 870–889 | CC press handler |
| `firmware/dev/code.py` | 922–942 | PC press handler |
| `config-editor/src-tauri/src/config.rs` | 22–30 | Rust `ButtonMode` enum |
| `config-editor/src/lib/types.generated.ts` | 65 | TS mode union |
| `config-editor/src/lib/components/ButtonRow.svelte` | 416–427 | Mode dropdown |
| `config-editor/src/lib/components/ButtonRow.svelte` | 382–390 | conditional `flash_ms` field |
| `config-editor/src/lib/formStore.ts` | 353–401 | `normalizeButton` (strip-on-serialize) |
| `tests/test_config.py` | 329–386 | existing PC mode tests (mirror pattern) |

---

## Implementation steps

### Step 1: schema + Python validator + tests (TDD)

**Files to edit:**
- `tests/test_config.py` — write tests **first**
- `config.schema.json`
- `firmware/dev/core/config.py`

**1a. Write failing tests in `tests/test_config.py`:**

Add a new test class `TestSelectMode` (or extend the existing PC mode test class) covering:

- `test_pc_select_mode_with_group_accepted`: `{"type": "pc", "mode": "select", "select_group": "amp", "program": 5}` → validates; preserves `mode`, `select_group`, default `select_repress == "resend"`.
- `test_cc_select_mode_with_group_accepted`: same shape for CC with `cc`/`cc_on` fields.
- `test_select_mode_missing_group_rejected`: `mode == "select"` with no `select_group` → validation error.
- `test_select_mode_empty_group_rejected`: `select_group == ""` → validation error.
- `test_select_mode_whitespace_only_group_rejected`: `select_group == "   "` → validation error (or trim then reject).
- `test_select_repress_default_is_resend`: `select_repress` not specified → defaulted to `"resend"`.
- `test_select_repress_accepts_resend_nothing_deselect`: each accepted; preserved.
- `test_select_repress_invalid_rejected`: e.g. `"foo"` → validation error.
- `test_pc_select_repress_deselect_preserved_but_noted`: PC with `select_repress == "deselect"` is preserved (do NOT coerce).
- `test_select_mode_rejected_on_pc_inc`: `{"type": "pc_inc", "mode": "select", ...}` → error or coerce-to-default. Pick coerce-to-default to match existing pattern; assert resulting `mode != "select"`.
- `test_select_mode_rejected_on_pc_dec`: same.
- `test_select_mode_rejected_on_note`: same.
- `test_select_mode_rejected_on_hid`: same.
- `test_select_mode_rejects_multi_keytime`: a select-mode button with multiple keytime configs (e.g. `keytime2.program`) → error or coerce. Decide: hard-reject is cleanest given the user already plans to refactor keytimes.
- `test_select_group_stripped_when_mode_not_select`: `{"type": "pc", "mode": "flash", "select_group": "amp"}` → `select_group` is dropped from validated output (mirrors `flash_ms` stripping behavior).
- `test_select_repress_stripped_when_mode_not_select`: same idea.

Run the test file; confirm all new tests fail.

**1b. Update `config.schema.json`:**

- Add `"select"` to the `ButtonMode` enum at `config.schema.json:58–61`.
- Add `select_group` and `select_repress` properties to the button object schema.
- `select_repress` enum: `["resend", "nothing", "deselect"]`.
- Schema-level required-when-select can be expressed via JSON Schema `if`/`then` if convenient; if not, the Python validator is authoritative.

**1c. Update `firmware/dev/core/config.py`:**

- At lines ~104–108, accept `"select"` in the mode-validation set, but only for `pc` and `cc` types. For other types, fall back to the type's default mode (matching how unknown modes are already handled).
- After mode is validated, if `mode == "select"`:
    - Read `select_group`. Strip whitespace. If empty/missing → raise validation error (or whatever this codebase uses for hard-reject; check how other required fields signal failure).
    - Read `select_repress`, default to `"resend"`. Validate against `{"resend", "nothing", "deselect"}` → reject if invalid.
    - Check for multi-keytime configs (look at how existing code detects keytime2/keytime3 fields). If present → reject.
    - Persist `select_group` and `select_repress` in the validated button dict.
- After mode is validated, if `mode != "select"`:
    - Drop `select_group` and `select_repress` from the validated dict (mirror how `flash_ms` is dropped when `mode != "flash"` at lines ~135–138).

**1d. Run tests until green.** All new tests pass; existing tests still pass.

### Step 2: Firmware (`firmware/dev/code.py`)

**2a. New helper near `flash_pc_button` (line ~748):**

```python
def update_select_group(active_btn_num, group):
    """Activate one select-mode button and deactivate its group siblings.

    Iterates all buttons; for each select-mode member matching `group`,
    sets state on iff (i+1 == active_btn_num). LED follows via set_button_state,
    which respects each button's own off_mode.

    Writes only LED + button_states; never sends MIDI. Safe to call from RX
    paths without infinite-loop risk.
    """
    if not group:
        return
    for i, cfg in enumerate(buttons):
        if cfg.get("mode") == "select" and cfg.get("select_group") == group:
            on = (i + 1) == active_btn_num
            button_states[i].state = on
            set_button_state(i + 1, on)
```

**2b. PC press handler (line ~922–942):**

Add a `select` branch alongside the existing `toggle`/`momentary`/`flash` branches. Pseudocode:

```python
elif mode == "select":
    group = btn_config.get("select_group", "")
    repress = btn_config.get("select_repress", "resend")
    is_active = btn_state.state  # already-active check
    if is_active and repress == "nothing":
        pass  # no MIDI, no LED change
    elif is_active and repress == "deselect":
        # PC: no-op in V1 (gated on #47). Treat as resend.
        midi_send(ProgramChange(program), channel=channel)
        # LED already on; group state unchanged
    else:  # inactive press, or active+resend
        midi_send(ProgramChange(program), channel=channel)
        update_status(f"TX PC{program}")
        update_select_group(btn_num, group)
```

(Match the surrounding code's exact style: `print` calls, `update_status`, etc.)

**2c. CC press handler (line ~870–889):**

Analogous select branch. CC `deselect` actually fires:

```python
elif mode == "select":
    group = btn_config.get("select_group", "")
    repress = btn_config.get("select_repress", "resend")
    is_active = btn_state.state
    cc_on = btn_config.get("cc_on", 127)
    cc_off = btn_config.get("cc_off", 0)
    cc_num = btn_config.get("cc", 0)
    if is_active and repress == "nothing":
        pass
    elif is_active and repress == "deselect":
        midi_send(ControlChange(cc_num, cc_off), channel=channel)
        update_status(f"TX CC{cc_num}={cc_off}")
        # Clear the active-member: this button off, no new active
        button_states[btn_num - 1].state = False
        set_button_state(btn_num, False)
    else:  # inactive press, or active+resend
        midi_send(ControlChange(cc_num, cc_on), channel=channel)
        update_status(f"TX CC{cc_num}={cc_on}")
        update_select_group(btn_num, group)
```

**2d. MIDI RX in `_process_midi_msg` (line ~790–820):**

After the existing `pc_values` / `button_states` updates, add a hook:

- If incoming is a PC: find any select-mode PC button with matching `(channel, program)`. If found, route through the same logic as 2b (treat as if pressed locally). Note: `update_select_group` does the LED/state work; the press handler logic decides resend/nothing/deselect for repeated incoming activations.
- If incoming is a CC: find any select-mode CC button with matching `(channel, cc_number)` whose `cc_on == received_value`. If found, route through 2c logic.

Extract the shared logic from 2b/2c into a helper if it cleans up duplication; otherwise inline.

**Important:** the RX path must be a function call to the same logic as the press path, not a copy-paste. Otherwise behavior diverges.

**2e. No persistence.** Boot state is whatever `button_states` initializes to — all off. Do not write anything to disk.

### Step 3: Rust config struct

**File:** `config-editor/src-tauri/src/config.rs`

- Add `Select` variant to the `ButtonMode` enum (line ~22–30). Use `#[serde(rename = "select")]` if needed for lowercase serialization (match existing variants).
- Add fields to the button struct:
    - `select_group: Option<String>`
    - `select_repress: Option<String>` (or a new `SelectRepress` enum with `Resend`/`Nothing`/`Deselect` if the codebase favors typed enums)

Run `cargo check` (or whatever the project uses) to confirm it compiles.

### Step 4: TS types + form normalizer

**File:** `config-editor/src/lib/types.generated.ts`

- Add `"select"` to the `mode` union at line ~65.
- Add `select_group?: string` and `select_repress?: "resend" | "nothing" | "deselect"` to the button type.

**File:** `config-editor/src/lib/formStore.ts` (`normalizeButton`, line ~353–401)

- For the `pc` and `cc` cases, after the existing flash-mode stripping logic:
    - If `common.mode === "select"`: include `select_group` and `select_repress` in the output. Strip `flash_ms`.
    - Else: strip both `select_group` and `select_repress` from the output.

**Form-state preservation:** the editor should hold `select_group` and `select_repress` in component-local state across mode flips, so flipping `select` → `flash` → `select` doesn't lose user input. The serialized JSON only contains them when `mode == "select"`. This is purely a UI concern — the normalizer is the gate.

### Step 5: Editor UI (`ButtonRow.svelte`)

**5a. Rename label:** at line ~418, change the dropdown label `LED Mode:` → `Mode:`.

**5b. Add Select option to Mode dropdown** for PC and CC types. The dropdown logic at line ~416–427 currently has `flash` (PC only), `toggle`, `momentary`. Add `select` for both PC and CC.

**5c. Conditional `select_group` field:** when `mode == "select"`, show a text input for `select_group`. Implement autocomplete from existing groups:
- Compute a derived list of unique `select_group` values across all buttons in the current config.
- Render as an `<input list="...">` with a `<datalist>` in the same component, or use whatever autocomplete pattern this codebase already uses (look at how `color` fields handle named-color autocomplete, if at all).

**5d. Conditional `select_repress` field:** when `mode == "select"`, show a dropdown with `resend` / `nothing` / `deselect`.

**5e. PC-deselect help text:** when the button is PC-typed and `select_repress` shows `deselect` as the selected value (or as an option), render help text below the dropdown:

> "Deselect requires multi-message support — tracked in #47."

The option itself should be **disabled** in the PC case (do not silently hide it; the user should see why it's unavailable). Avoid `<option disabled title="...">` patterns — Tauri webview tooltip support on `<option>` is unreliable. Use the help-text line below the dropdown instead.

**5f. Hide `flash_ms`:** the existing condition at line ~382–390 already hides `flash_ms` when `mode !== "flash"`. Verify it still works after adding `select` to the mode union.

### Step 6: Docs (`AGENTS.md`)

Find the existing button-mode documentation. Add:

- Documentation for `mode: "select"`, `select_group`, `select_repress`.
- Note in whatever section describes future page handling: "Page-restore must repaint LEDs from `button_states[i].state` for select-mode buttons. Do not reinit from config defaults — that would lose latched group state."

If there's no existing place for the page-handling note, add a TODO/comment near the page-related code (if any exists).

### Step 7: Manual hardware smoke test (user-driven, not Claude)

This is for the user to run after a successful build/deploy. Document the steps in the PR description:

1. Configure 3 PC buttons in the same `select_group`, different `program` values.
2. Press each in turn — verify exclusive LED behavior, verify TX MIDI is correct.
3. Configure a 4th button in a *different* `select_group` — verify it doesn't interact with the first three.
4. Test `select_repress` modes: `resend` (default), `nothing`, `deselect` (CC only).
5. From a host (Gig Performer or equivalent), send PC matching one of the buttons — verify the LED activates and siblings deactivate.
6. Same for CC: send `cc_on` value — verify activation; send a non-`cc_on` value — verify no activation.
7. Verify boot: device powers up with all select-mode LEDs off.

---

## Out of scope for V1 (do not implement)

- **Off-message on sibling deactivation.** Optional in #43's spec; depends on #47 (multi-message-per-press). When a sibling is deselected, its LED goes off and **no MIDI is emitted on its behalf**.
- **Multi-group membership per button.** `select_group` is a single string, not an array. Backwards-compatible upgrade path exists if needed later.
- **Note-button select.** Note is gate-style; out.
- **`pc_inc`/`pc_dec` select.** Increment in a radio group is incoherent.
- **Page scoping of select groups.** Pages aren't built yet. Defer entirely.
- **Reboot persistence of active group member.** Boot dark.
- **Bidirectional sync beyond the simple RX hook.** No broader mirror-host-state work.
- **Lone-wolf select-button validator warning.** Skipped.
- **Boot-default-active per group (`select_default`).** Skipped.
- **Refactoring keytimes** (separate user concern; out of scope here).
- **PC `select_repress: "deselect"` firmware behavior** (gated on #47; field is preserved through validation only).

---

## Verification before claiming done

- [ ] All new tests in `tests/test_config.py` pass; full test suite still passes.
- [ ] Rust + Svelte builds succeed with no new warnings.
- [ ] Editor: changing Mode → Select shows `select_group` + `select_repress` fields; flipping back hides them; serialized JSON drops them when not in select mode.
- [ ] Editor: autocomplete for `select_group` shows existing group names from elsewhere in the config.
- [ ] Editor: PC + Select shows `Deselect` disabled with help-text; CC + Select allows all three options.
- [ ] AGENTS.md updated.
- [ ] Code review requested via the `requesting-code-review` skill before opening a PR.
- [ ] PR description includes the manual hardware smoke-test checklist for the user to run.
