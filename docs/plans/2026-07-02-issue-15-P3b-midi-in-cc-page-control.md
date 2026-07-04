# Issue #15 P3b — MIDI-IN CC Page Control (Design + Plan)

**Date:** 2026-07-02
**Branch:** `15-pages-p3b`
**Phase:** P3b. Follows P2 (runtime `switch_page()` mechanism) and P3 (button-triggered
`page_inc`/`page_dec`/`page_jump`). Delivers the last page-switch trigger the issue
names: an inbound MIDI **Control Change** from a host/DAW/foot controller changes the
active page.

## Goal

Let an external device switch the active page by sending a CC. Reuse the P2/P3
machinery unchanged: pure index math in `resolve_page_target`, and the
deferred-switch `pending_page_target` global drained by `handle_switches()`.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Schema shape | **Structured `jump`/`inc`/`dec` slots** (Option B) | Covers full scope (jump + inc/dec) in one device-level block. Fixed 3-slot shape → clean editor UI later (3 rows, no list management). Matches the existing `page_jump`/`page_inc`/`page_dec` action vocabulary from P3. |
| Scope | **jump + inc/dec** | Full issue scope. inc/dec are nearly free — they reuse `resolve_page_target`. |
| `jump` value semantics | **Incoming CC value = absolute page index**, clamped | OEM parity (`CC 20 XX` → jump to page `XX`). |
| `inc`/`dec` value semantics | **Value is a trigger gate**, not a page number | Fires only when the incoming value equals the slot's `value` (default 127). Without a gate, `inc` would fire on *every* value including 0. Moves by `page_step`, wraps. |
| Channel filter | **`channel: null` (or omitted) = any channel**; int = that channel only | DAWs blast CCs on many channels; opt-in filtering. Consistent with device `in_channel=None`. |
| Precedence vs button CCs | **page_control wins; short-circuit** | A CC that matches a page_control slot switches the page and returns — it is NOT also processed as a button CC. Page CCs are dedicated control inputs. |
| Editor form UI | **Deferred to P4** | Same split P3 used (per-field `page_step`/`page` inputs also deferred to P4). P3b ships schema + generated types + firmware + validation; the editor widget lands in P4. |

## Config shape

Device-level (top-level) optional block:

```json
"page_control": {
  "enabled": true,
  "channel": null,
  "jump": { "cc": 20 },
  "inc":  { "cc": 21, "value": 127, "page_step": 1 },
  "dec":  { "cc": 22, "value": 127, "page_step": 1 }
}
```

Behavior (2-page device shown; wrap/clamp per `resolve_page_target`):

| Inbound | Result |
|---|---|
| `CC20 val 1` | jump to page 1 (clamp to range) |
| `CC20 val 99` | jump clamped to last page |
| `CC21 val 127` | page +1 (wrap past last → 0) |
| `CC22 val 127` | page −1 (wrap past first → last) |
| `CC21 val 0` | ignored (value ≠ gate) |
| any CC on filtered-out channel | ignored |
| omitted slot | that action disabled |
| `enabled: false` or block absent | no inbound CC affects pages |

## Firmware design

New pure helper in `core/config.py`, unit-tested, no device deps:

```python
def resolve_page_control(pc, cc, value, channel, current, num_pages):
    """Target page index for an inbound CC under page_control, or None.

    None when page_control is absent/disabled, the channel is filtered out, or no
    slot matches (caller leaves the page unchanged). jump uses `value` as the
    absolute target; inc/dec fire only when value == the slot's gate `value`.
    """
    if not pc or not pc.get("enabled", True):
        return None
    ch = pc.get("channel", None)
    if ch is not None and ch != channel:
        return None
    jump = pc.get("jump")
    if jump and jump.get("cc") == cc:
        return resolve_page_target(current, num_pages, "jump", value)
    inc = pc.get("inc")
    if inc and inc.get("cc") == cc and value == inc.get("value", 127):
        return resolve_page_target(current, num_pages, "inc", inc.get("page_step", 1))
    dec = pc.get("dec")
    if dec and dec.get("cc") == cc and value == dec.get("value", 127):
        return resolve_page_target(current, num_pages, "dec", dec.get("page_step", 1))
    return None
```

Wiring in `code.py::_process_midi_msg`, top of the `ControlChange` branch (before the
button-match loop), declaring `global pending_page_target` at function scope:

```python
tgt = resolve_page_control(
    config.get("page_control"), cc, val, msg_channel,
    config.get("active_page", 0), len(config.get("pages", [])))
if tgt is not None:
    pending_page_target = tgt
    print(f"[PAGE] CC{cc}={val} -> page {tgt}")
    update_status(f"PAGE {tgt + 1}")
    return
```

**Deferred-switch invariant holds.** Main loop order is `handle_midi()` →
`handle_switches()` (`code.py:1597`). `handle_midi()` only *sets*
`pending_page_target`; `handle_switches()` drains it after its scan loop the same
iteration. Never call `switch_page()` inline — it rebuilds `buttons[]` and would
corrupt the button-match loop `_process_midi_msg` is mid-way through.

## Validation

- **`core/config.py`** loader: sanitize `page_control` — `enabled` bool (default
  True); `channel` int 0–15 or None; each slot's `cc` clamped 0–127; `value`
  clamped 0–127 (default 127); `page_step` int ≥1 (default 1). Drop malformed
  slots rather than crash (firmware never rewrites disk).
- **`config.rs`** `MidiCaptainConfig`: add `page_control: Option<PageControl>` with
  `#[serde(skip_serializing_if = "Option::is_none")]`; add `PageControl` /
  `PageControlJump` / `PageControlStep` structs; extend `validate()` with the same
  range checks (CC 0–127, channel 0–15, page_step ≥1).

## Files (3-layer schema tax + firmware + tests)

1. `config.schema.json` — add `page_control` to top-level `properties`; add
   `PageControl` / `PageControlJump` / `PageControlStep` to `definitions`.
2. `config-editor/src/lib/types.generated.ts` — regenerate from schema.
3. `config-editor/src-tauri/src/config.rs` — structs + `validate()`.
4. `firmware/dev/core/config.py` — `resolve_page_control()` + loader sanitize.
5. `firmware/dev/code.py` — wire into `_process_midi_msg` ControlChange branch.
6. `tests/test_config.py` — unit tests for `resolve_page_control` (jump clamp,
   inc/dec wrap, gate mismatch, channel filter, disabled, absent block).
7. Rust tests in `config.rs` — validation range coverage.
8. `firmware/AGENTS.md` — replace the "deferred to P3b" note with the shipped design.

## Test plan

- `resolve_page_control` unit tests: jump absolute+clamp; inc/dec wrap; value gate
  reject; channel filter (match / mismatch / null=any); `enabled:false` → None;
  absent block → None; `num_pages<=1` → 0 (delegated to `resolve_page_target`).
- Rust: valid block round-trips; out-of-range cc/channel/page_step rejected.
- On-device (manual, deferred to hardware pass): 2-page config, send `CC20 XX` from a
  MIDI monitor → page jumps; `CC21 127` → +1; verify screen/LEDs repaint.
- `test-all.sh` green (pytest, cargo test, svelte-check, ruff, mpy-cross, clippy).

## Deferred to P4

- Editor form widget for `page_control` (CC/value/channel/page_step inputs).
- Per-field `page_step`/`page` inputs on button page types (already P4).
