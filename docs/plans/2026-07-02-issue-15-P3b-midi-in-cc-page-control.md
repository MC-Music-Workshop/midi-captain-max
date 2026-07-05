# Issue #15 P3b — MIDI-IN CC Page Control (Design + Plan)

**Status:** Shipped — merged in PR #161; #15 (Pages parity) remains open for later phases.
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
| `jump` value semantics | **Incoming CC value = absolute page index (0-based)**, clamped | OEM parity (`CC 20 XX` → jump to page `XX`). **⚠ Confirm on hardware:** value is treated as a 0-based index (`val 1` → second page). If the OEM numbers pages 1-based, the jump path needs a `-1` offset. Verify against a real controller before shipping. |
| Slot precedence within page_control | **Checked `jump` → `inc` → `dec`; first match wins** | Deterministic order. If two slots share a `cc` with the same gate, the earlier one wins and the later is unreachable — that's a config error, not a supported mode. |
| Shared `cc`, different gates | **Supported** (`inc {cc:21,value:127}` + `dec {cc:21,value:0}`) | The fall-through structure lets one CC drive both directions via distinct value gates — encoder-style up/down on a single CC. Deliberate, tested. |
| `inc`/`dec` value semantics | **Value is a trigger gate**, not a page number | Fires only when the incoming value equals the slot's `value` (default 127). Without a gate, `inc` would fire on *every* value including 0. Moves by `page_step`, wraps. |
| Channel filter | **`channel: null` (or omitted) = any channel**; int = that channel only | DAWs blast CCs on many channels; opt-in filtering. Consistent with device `in_channel=None`. |
| Precedence vs button CCs | **page_control wins; short-circuit button processing** | A CC that matches a page_control slot switches the page and returns from `_process_midi_msg` — it is NOT also processed as a button CC. Page CCs are dedicated control inputs. **Note:** short-circuit only skips button matching; `handle_midi()` still forwards the raw CC downstream via MIDI THRU (`code.py:1037-1065`) — THRU stays transparent. |
| Same-page jump | **No-op (guard in wiring), but still short-circuit** | `switch_page()` never no-ops — it rebuilds `buttons[]` and resets latch/keytimes/encoder state even for the current page. A DAW re-sending `CC20=<current>` (scene recall, snapshot spam) would wipe latch state on every message. Wiring skips setting `pending_page_target` when target == current, but still `return`s: the CC matched a dedicated page slot either way. |
| Malformed `cc` in a slot | **Drop the slot** (with `[CONFIG WARN]`), never clamp | Clamping `cc: 300` → 127 would make the device silently listen on CC 127 — a wrong CC number means wrong behavior, not degraded behavior. (`value`/`page_step` ARE clamped: same intent, degraded range.) |
| Malformed `channel` | **Disable the whole block** (with `[CONFIG WARN]`) | `channel: null` means "any channel" — so coercing a bad value to `None` would *widen* matching from one channel to all channels, the opposite of a safe fallback. A malformed channel likely means the user meant to scope to one channel and mistyped it; silently defaulting to "any channel" turns a scoping typo into every CC on every channel jumping pages (risk during a live set). `channel` is shared by all 3 slots, so a bad value can't be dropped per-slot without ambiguity — the disable blast radius is the whole block, one tier stricter than the per-slot `cc` drop below. This has no direct precedent elsewhere in the `core/config.py` loader (existing fields clamp-to-default, e.g. bad `page_step` → 1); it's a new fail-closed convention introduced here, not a reused pattern. |
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
| shared `cc`: `inc{cc:21,val:127}` + `dec{cc:21,val:0}`, `CC21 val 127` | page +1 (inc gate matches) |
| shared `cc` (as above), `CC21 val 0` | page −1 (dec gate matches) |
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
    # Same-page guard: switch_page() has no no-op path — it rebuilds buttons[]
    # and resets latch/keytimes state. Skip the switch when already there, but
    # still return: a matched page CC is a dedicated input either way.
    if tgt != config.get("active_page", 0):
        pending_page_target = tgt
        print(f"[PAGE] CC{cc}={val} -> page {tgt}")
        update_status(f"PAGE {tgt + 1}")
    return
```

(`resolve_page_control` needs adding to the `core.config` import list at `code.py:49`.)

**Deferred-switch invariant holds.** Main loop order is `handle_midi()` →
`handle_switches()` (`code.py:1599`). `handle_midi()` only *sets*
`pending_page_target`; `handle_switches()` drains it after its scan loop the same
iteration. Never call `switch_page()` inline — it rebuilds `buttons[]` and would
corrupt the button-match loop `_process_midi_msg` is mid-way through.

## Validation

- **`core/config.py`** loader: sanitize `page_control` — `enabled` bool (default
  True); `channel` must be int 0–15 or None, anything else **disables the block**
  with `[CONFIG WARN]` (fail closed — coercing to None would widen matching to
  all channels); each slot's `cc` must be int 0–127, otherwise **drop the slot**
  with `[CONFIG WARN]` (never clamp — a wrong CC number is wrong behavior, not
  degraded behavior); `value` clamped 0–127 (default 127); `page_step` int ≥1
  (default 1). Firmware never rewrites disk.
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
- Loader sanitize tests: slot with non-int / out-of-range `cc` dropped (not
  clamped); malformed `channel` disables block; valid slots survive alongside a
  dropped one.
- Precedence: `jump.cc == inc.cc` (same gate) → jump wins, inc unreachable.
- Shared `cc`, different gates: `inc{cc:21,value:127}` + `dec{cc:21,value:0}` —
  `val 127` → inc target, `val 0` → dec target (locks in the encoder-style mode).
- `enabled` key absent → defaults true (block active).
- Wiring/behavior: jump to the current page leaves `pending_page_target` unset
  (same-page guard) — assert via `resolve_page_control` + guard condition.
- Rust: valid block round-trips; out-of-range cc/channel/page_step rejected.
- On-device (manual, deferred to hardware pass): 2-page config, send `CC20 XX` from a
  MIDI monitor → page jumps; `CC21 127` → +1; verify screen/LEDs repaint.
- `test-all.sh` green (pytest, cargo test, svelte-check, ruff, mpy-cross, clippy).

## Deferred to P4

- Editor form widget for `page_control` (CC/value/channel/page_step inputs).
- Per-field `page_step`/`page` inputs on button page types (already P4).
