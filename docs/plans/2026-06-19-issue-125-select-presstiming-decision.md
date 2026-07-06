# Decision: select-mode × press-timing (Issue #125)

**Status:** Decided — Option 1 (keep flat), no code change; #125 closed. Revisit if a real use case demands it.
**Issue:** https://github.com/MC-Music-Workshop/midi-captain-max/issues/125
**Decided:** 2026-06-19
**Depends on (all landed):** #43 (select mode), #48 (press-timing model), #47 (multi-message).

---

## TL;DR

`mode: "select"` and `mode: "keytimes"` stay **separate, mutually-exclusive mode families**. A button is one or the other, never both. Select buttons have no `short[]`/`long[]`; keytimes buttons have no `select_group`. This is what already shipped after #48 — this doc ratifies it as intentional, not accidental.

User-facing framing: *keeping it simple for now; if we hit walls or identify a concrete use case, we revisit.*

## Current state (the shipped design)

- `mode: "keytimes"` (#48): press-timing model. Messages live in `short[]`/`long[]` `KeytimesEntry` arrays. Short vs long press picks the array; re-press advances the cycle index. No group semantics.
- `mode: "select"` (#43): radio group. Button-level `select_group` + `select_repress`. Single message (`pc`/`cc` only), `keytimes == 1` enforced by the validator. No press-timing.

The validator routes `mode: "keytimes"` to a dedicated path (`_validate_keytimes_button`) and `mode: "select"` through the legacy path with `select_group`/`select_repress`. The two never mix — see `firmware/dev/core/config.py` and `config-editor/src-tauri/src/config.rs`.

## Why flat

- **Simple uniform rule.** Two clean families beat one family with conditional sub-behavior. No combined state machine to reason about.
- **The only thing the alternatives buy** — long-press to switch within a radio slot, or multi-state group members — is speculative. No board need has surfaced.
- **Zero new surface.** No new validator rules, firmware dispatch, schema fields, or editor UI. Nothing new to test or break.

## Cost of NOT doing the alternatives

A user who wants both behaviors must pick one per button. There is no "radio member that also has a long-press action." If that turns out to be common, reopen with a concrete config example and reconsider Option 3 below.

---

## Alternatives considered (for the revisit)

### Option 2: select per cycle entry

Move `select_group`/`select_repress` down to the `KeytimesEntry` level so each timing slot can belong to a different group.

- **Buys:** maximum flexibility — every entry independently radio-controlled.
- **Cost:** full group state machine rework; group membership becomes per-entry-per-press. Hardest to reason about. RX matching and page-restore both explode in complexity.
- **Verdict:** rejected. Flexibility nobody asked for, highest cost.

### Option 3: hybrid — top-level `select_group` on a keytimes button

Lift `select_group`/`select_repress` to the **top level** of a `keytimes`-mode button. Group membership stays button-level (as today); cycle entries supply the messages.

How it would look:

```jsonc
{ "mode": "keytimes", "type": "pc",
  "select_group": "amp", "select_repress": "resend",   // radio membership
  "short": [ { "down": [{"type":"pc","program":5}], "color":"green" } ],
  "long":  [ { "down": [{"type":"pc","program":9}], "color":"red"   } ] }
```

Semantics: any timing event (short or long) marks the button active in its group and dims siblings; the fired message is whatever the current cycle entry holds.

**Buys:** a radio member can have short/long behavior and can itself be multi-state.

**Open questions to resolve before implementing (the hard part):**

1. **Re-press × cycle-advance collision.** `select_repress` (`resend`/`nothing`/`deselect`) vs cycle index advance — which wins on re-press of the active member? Needs an explicit combined rule.
2. **Sibling reset.** When a different member is selected, does the deactivated button's cycle index reset to 0 or freeze? Pick one, store it.
3. **RX match becomes many-to-one.** #43 lights a member when incoming PC/CC matches its `(channel, program/cc)`. With cycle entries, which entry's message is matched — first only, or any of `short[]`+`long[]`? The clean 1:1 match is gone.
4. **Pages (#15) restore surface.** Page-restore already repaints group LEDs from `button_states[i].state` (see `firmware/AGENTS.md`). Hybrid adds per-button cycle index to also save/restore per page.

**Implementation sketch (if revisited):**

- `config.rs` + `config.py`: allow `select_group`/`select_repress` on `mode: "keytimes"`; keep `pc`/`cc`-only constraint or widen deliberately. Regenerate `types.generated.ts`.
- Firmware: in the keytimes dispatch branch (`dispatch_keytimes_events`), after firing, call `update_select_group(btn_num, group)`. Resolve the four open questions above as explicit rules first.
- `_process_midi_msg`: extend RX matching to scan a keytimes button's entry messages (decide first-only vs any).
- `ButtonRow.svelte`: render group fields alongside the cycle editor when `mode == "keytimes"`.
- Likely multi-PR. Drive it with its own design doc once the four questions are answered.

**Verdict:** deferred, not rejected. This is the path if the revisit happens.
