# Press Timings & Long-Press Implementation Plan (#48)

**Status:** Shipped — #48 closed; `mode: "keytimes"` is in the current firmware.
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add OEM-parity press-timing support to footswitches as a **new mode** (`mode: "keytimes"`) — short/long press detection with independent message cycles per button. Existing modes (`toggle`, `momentary`, `flash`, `select`) are unchanged.

**Architecture:** A new button mode `keytimes` opts into a rich press-timing + multi-state cycle model: two independent cycles per button (`short`, `long`), each an array of entries with optional `down`/`up`/`color`/`dim`/`label` sub-fields. A polling-loop threshold timer in the firmware detects when a held button transitions from "short" to "long" classification. Cycle state lives in a per-page table in RAM (per-page model is forward-compatible with #15). The schema reserves array-of-messages per slot (single-element today, multi-element later per #47). Buttons in any other mode use their existing dispatch path and config shape, completely untouched.

**Tech Stack:** CircuitPython firmware (Python), pytest for firmware tests, JSON schema for config validation.

**Resolves:** #48 (this issue), #73 (external-contributor parity request), partially feeds #15 (pages) and #47 (multi-message).
**Closes:** #14 (already closed as duplicate of #73).
**Forward-links:** #15 (pages), #47 (multi-message per slot), #123 (CC ramp), #125 (select-mode + keytimes compatibility).

**Deprecation (v2.0) + Breaking change (v3.0):** The `keytimes: N` + `states[]` fields on `mode: "toggle"`/`"momentary"` buttons are **deprecated** in v2.0 and will be **removed** in v3.0. v2.0's validator continues to process them (legacy behavior preserved — users' existing buttons keep working) but prints a loud boot-time warning per affected button pointing to `mode: "keytimes"`. v3.0 will drop the field handling entirely. The user base is small and the new mode is a strict superset of what `keytimes` + `states[]` could do, so migration is mechanical; the soft-deprecation period exists only to avoid silently breaking buttons during upgrade.

The strict-rejection alternative was considered and rejected: dropping the legacy fields silently in v2.0 would turn cycling buttons into single-state buttons with no visible explanation, which is worse UX than a warning-plus-functional. v3.0 can do the hard cut once users have had time to migrate (and once the warning has been visible for a release).

---

## Design Summary

### The Four Trigger Timings

| Slot | Fires when |
|---|---|
| `short_down` | Button physically goes down, *before* the long-press threshold elapses. Always fires on every press (short or long) if defined. |
| `short_up` | Button is released *before* the threshold elapses (i.e. a "tap-and-release"). Does NOT fire if the press became long. |
| `long_down` | Threshold elapsed while still held. The press has been classified as long. |
| `long_up` | Button is released *after* the threshold elapsed (i.e. release of a long press). |

`short_up` is the only slot that doesn't fire under all conditions — this is deliberate and matches OEM. Doc this as a "tap" semantic.

To fire a message regardless of duration:
- On the press → bind `short_down`. It fires on every physical press.
- On the release → bind the same message to both `short_up` AND `long_up`.

### Cycles

Each button has **two independent cycles**: `short` and `long`. Each is an array of entries. Each entry has optional `down`, `up`, `color`, `dim`, and `label` sub-fields. The down/up of the same entry are paired by physical press (same as OEM's `short_dwN`/`short_upN` pairing by N).

- `color` — named color from the existing palette. `"off"` means LED dark. Missing means inherit the previous entry's value within this cycle.
- `dim` — boolean. When true, the resolved color is rendered through `dim_color()` (15% brightness, reusing existing `core/colors.py:34`). Lets a cycle entry represent a "muted" state without introducing new color names.
- `label` — optional text override for the TFT display. Missing or empty string means inherit from the button-level `label`. Same inherit rule across the cycle as `color`.

**Advancement rule:** Per cycle, per physical press — advance by 1 if ≥1 of that cycle's events fired **with slot content** during the press; else don't advance. An event whose slot is empty does not advance the cycle (same rule as MIDI dispatch and LED render — see Render-Update Trigger below).

So a short tap with both `short_down` and `short_up` populated → both fire, short cycle advances **by 1** (not 2). A long press with `long_down` populated but `short_down` empty → only the long cycle advances. The short cycle stays put, which is what you want for the reverb+shimmer scenario: holding to toggle shimmer must not silently shift your reverb cycle.

### Threshold

- `long_press_threshold_ms` is a top-level config field. Default **500ms**.
- Each button may set its own `long_press_threshold_ms` override.
- Resolution: button override if set, else global, else 500.

### Color Render Rule

Each cycle's current entry carries an optional `color`. The two layers combine as:

```
if short.color == "off":     LED = off          (kill switch — short "off" overrides all)
elif long.color is set:      LED = long         (decoration over primary)
elif short.color is set:     LED = short
elif button.color is set:    LED = button.color (fallback for "(inherit)" entries)
else:                        LED = off
```

An entry with no `color` field — "(inherit)" in the editor — means **no override**: the layer's color clears on that entry and the LED falls back to the button-level `color` field. An explicit `"off"` is distinct from unset: `"off"` overrides; `(inherit)` does not.

> **Revision (beta.9 follow-up, #143):** the rule above describes `compute_keytimes_led_color()`, which resolves whatever layers it's handed. At *render* time `_render_keytimes_led()` no longer hands it both layers — it passes only the **last-fired** timing class (short or long), suppressing the other. So the last press's class fully owns BOTH the LED color and the label text until the other class fires; before the first press both fall back to the button-level color/label.
>
> Why: a text label shows one string and the LED one color, so a long layer can't *compose* on top of short — it just clobbers. The original `long_label or short_label` precedence never cleared the long layer, so the first long press left the long label/color stuck on every subsequent short press. Tester report: "Long label always sticks" — repro is long-press then short-press (order-dependent, which is why it evaded earlier testing). Last-fired ownership fixes both the label and the LED.

Note: this is *not* "inherit the previous entry's color". An earlier draft of #48 carried the previous entry's color forward, but that caused a wrap-around surprise — a kill-switch `"off"` entry would persist through subsequent inherit entries because the inherit didn't clear the layer. The current rule is per-entry: each press resets the layer to exactly what the entry specifies, or to the button-level fallback if the entry specifies nothing.

The asymmetry (`"off"` on short kills the LED but `"off"` on long is just "no decoration") matches the physical pedalboard metaphor: short is the primary indicator, long is a decoration painted over it; with no primary, there's nothing to decorate.

### Slot-Has-Content Rule (MIDI + LED + Cycle Advancement)

A single rule governs all three axes: **an event whose slot has no messages does nothing.** No MIDI fires, the LED render state doesn't update, and the cycle doesn't advance.

The slot the user populates is the slot where stuff happens. Concretely:
- A config with only `short_up` populated → LED changes on tap-release. No flash on press. Long press does not advance the short cycle (no short MIDI fired).
- A config with `long_down` populated → LED changes (and MIDI fires) at the threshold.
- A config with `long_up` populated → LED changes (and MIDI fires) at release of a long press.
- An entry with no messages on either slot (color-only) does nothing — no render, no advance. If you want a colored cycle position, give it at least one message.

This is intentional. An earlier draft had cycle advancement triggered by any event firing (including empty `short_down` during a long press), which silently shifted the short cycle every time you held the button. That's now fixed.

### Cycle State Lifecycle

| Event | Cycles reset? |
|---|---|
| Power cycle / boot | Yes (RAM is volatile) |
| Config push from editor | Yes (triggers reboot) |
| Page change away & back (after #15 lands) | No (sticky per page) |
| In-flight press when page changes | Press cancelled; no events fire |

In-flight cancellation is the chosen behavior. Alternatives **(b)** "press continues against original page" and **(c)** "press rebinds to new page" are documented in this plan and the user-facing docs as considered-but-rejected, in case a future use case justifies them.

### Reserved Slots (Future)

- `hold` — continuous repeating action while held (re-send the same message every N ms). Tracked separately from `long`. Initially unimplemented; schema reserves the key.
- CC ramp (#123) — interpolate a CC value while held. Out of scope for #48.

### Schema Shape

A button opts into the new cycle/timing model by setting `mode: "keytimes"`. The `short` and `long` arrays are valid **only** on keytimes-mode buttons; the validator rejects them elsewhere. Existing modes (`toggle`, `momentary`, `flash`, `select`) keep their current configuration shape unchanged.

```json
{
  "label": "VERB",
  "mode": "keytimes",
  "color": "blue",
  "long_press_threshold_ms": 500,
  "short": [
    { "down": [{ "type": "cc", "cc": 20, "value": 127 }], "color": "white", "label": "VERB+" },
    { "down": [{ "type": "cc", "cc": 20, "value": 0   }], "color": "white", "dim": true }
  ],
  "long": [
    { "down": [{ "type": "cc", "cc": 21, "value": 127 }], "color": "blue"  },
    { "down": [{ "type": "cc", "cc": 21, "value": 0   }], "color": "white" }
  ]
}
```

Each sub-action (`down`, `up`) is an **array** of message objects, even when there's only one. This reserves the shape for #47 (multi-message per slot) without future migration. Initial firmware reads index `[0]` only; later firmware iterates the full list.

Message objects use the existing `type`-discriminated shape (`{type: "cc", cc, value}`, `{type: "pc", program}`, `{type: "note", note, velocity}`, `{type: "hid", action, key, modifier, delay_ms}`). This converges with the unified-message-types plan (`docs/plans/2026-03-01-unified-message-types.md`).

### Other Modes (unchanged)

`mode: "toggle"`, `"momentary"`, `"flash"`, and `"select"` retain their current schemas verbatim — button-level `cc`/`cc_on`/`cc_off`, `note`/`velocity_on`/`velocity_off`, `program`, `pc_step`, `hid_*` fields, `color`, `off_mode`, `channel`, `flash_ms`, `select_group`, `select_repress`. A user who just wants a stomp picks `momentary`; a latching effect uses `toggle`; rich multi-state/long-press behavior uses `keytimes`. Nothing in the new mode disturbs the simple cases.

The one schema change for non-keytimes modes: the legacy `keytimes: N` + `states[]` fields are **removed** from `toggle`/`momentary` (they previously enabled multi-state cycling on those modes). That role is now exclusively `mode: "keytimes"`'s job. Validator emits a clear error on configs that try to use them outside keytimes mode.

---

## Design Rationale & Alternatives Considered

This section preserves the *why* behind the choices so future contributors don't re-litigate them.

### Why two independent cycles instead of one shared

A user's real OEM config: short-press 1 = reverb on, short-press 2 = reverb off, long-press 1 = shimmer on, long-press 2 = shimmer off. This only works if short and long maintain independent counters — otherwise a hold in the middle of a sequence would scramble the short cycle.

OEM does the same: `short_upX` and `longX` increment their X separately.

**Rejected:** one shared cycle index across both short and long. It collapses the two-effect-per-button pattern into a single sequence, which is strictly less expressive than OEM and breaks the reverb+shimmer scenario.

### Why cycle lengths are independent

OEM uses a single `keytimes` count covering all four timing slots on a button (so `short_dwN`, `short_upN`, `longN`, `long_upN` all share the same N — though the short and long *counters* advance independently). The new model decouples the lengths too: `short` and `long` are independent arrays with independent lengths.

The reverb+shimmer scenario above happens to use length 2 for both cycles. But a button can legitimately have `short.length == 3` and `long.length == 2` — e.g., a "Lead" footswitch where:

- Tap cycles through three gain stages: Clean → Crunch → Lead → (back to Clean)
- Hold cycles through two ambient modes: Hall reverb → Plate reverb → (back to Hall)

**In the new model**, that's five entries total — three in `short`, two in `long`:

```json
"short": [
  { "down": [...Clean ...], "label": "CLEAN"  },
  { "down": [...Crunch...], "label": "CRUNCH" },
  { "down": [...Lead  ...], "label": "LEAD"   }
],
"long": [
  { "down": [...Hall ...], "label": "HALL"  },
  { "down": [...Plate...], "label": "PLATE" }
]
```

**Under OEM**, the shared `keytimes` count forces you to the lowest-common-multiple of the two cycle periods — here `LCM(3, 2) = 6`. That's *twelve* slot definitions (six short, six long), with values repeated to keep both cycles aligned:

```
keytimes = 6
short_up_1 = Clean,  long_1 = Hall
short_up_2 = Crunch, long_2 = Plate
short_up_3 = Lead,   long_3 = Hall
short_up_4 = Clean,  long_4 = Plate
short_up_5 = Crunch, long_5 = Hall
short_up_6 = Lead,   long_6 = Plate
```

This works because OEM advances the short and long counters independently — but the user pays for it with redundant entries and a DRY violation: change Clean's CC value and you must update slots 1 and 4 in lockstep; same for every other repeated state. The new model expresses the user's actual intent (three taps, two holds) without forcing them through the LCM-padding ceremony. A future contributor tempted to "fix" this by collapsing back to a single count should know it's intentional — the asymmetric case is what makes the model strictly more expressive than OEM.

### Why pair `down`/`up` within an entry instead of independent timing sequences

OEM pairs `short_dwN` and `short_upN` by N — both reference "the Nth short press." Within a single physical press, the down and up events are bookends of the same event, so they must use the same cycle index.

**Rejected:** separate `short_down: [...]`, `short_up: [...]` arrays with independent counters. This would mean down and up could desynchronize, which isn't physically possible (every down has a matching up). Pairing inside one entry object is correct.

**Rejected:** wrapper renames `short_press_cycle`/`long_press_cycle`, nested `cycles.short`/`cycles.long`, per-entry `n` field for explicit indexing. The schema as proposed already matches OEM's pairing-by-index semantics; further naming changes added clutter without clarity. The doc and examples carry the burden of teaching the pairing.

### Why "long modifies short" for color, with `"off"`-on-short as kill switch

Pedalboard mental model: the short cycle is the *primary* effect indicator. The long cycle is a *decoration* (secondary effect) painted on top. When the primary is off, the LED is dark — there's nothing for the decoration to attach to.

Concretely, this preserves the user's traced expectation: with reverb (short=white) + shimmer (long=blue), the LED is blue while both are on. Hit short again to turn reverb off (short=`off`); LED goes dark even though shimmer is still on, because there's no primary effect to color.

**Rejected:** symmetric override ("long always wins when set"). Loses the kill-switch semantic and surprises users who turn off the primary effect.

> **Superseded at render time (beta.9, #143):** "long always wins when set" is exactly the bug that shipped — `long_label or short_label` with no clear path meant the long layer stuck after the first long press. The composition rationale above still describes `compute_keytimes_led_color()` in isolation, but the live render now shows only the last-fired class (see the Color Render Rule revision note). The reverb+shimmer trace still holds because each step's expectation matches the most recent press; what changes is that a stale long layer no longer bleeds onto later short presses.

**Rejected:** RGB blending of short + long colors. Cute but unpredictable and impossible to reason about during a gig.

**Deferred:** opt-in inversion flag `color_priority: "short" | "long"`. YAGNI — no concrete use case. If one surfaces, easy to add as a button-level flag without migration.

### Why `hold` is reserved for the repeating flavor only

"Continuous on/off while held" (CC-on at threshold, CC-off at release) is already expressible via `long_down` (on) + `long_up` (off). No new slot needed. Reserving `hold` exclusively for the repeating-while-held flavor avoids overloading the term.

CC ramp (continuous interpolation while held) is filed separately as #123 — different enough to merit its own field, not just a `hold` variant.

### Why keytimes is a dedicated mode instead of a universal replacement

The first version of this design replaced toggle and momentary altogether — every button moved to the new shape, with a 2-entry cycle for "old toggle" and a single-entry-with-down+up for "old momentary." That approach buckled under its own ambition:

- It forced a migration on every existing button regardless of need
- It required render-side heuristics ("when entry has both down and up, treat as momentary") to recover behavior the old modes expressed directly
- It removed `off_mode` (a button-level field) and tried to express the same intent via per-entry `color`/`dim`, which got tangled
- It generated extended discussion of "Option A vs Option C" migration strategies that don't apply if no migration is required

The right framing: **toggle and momentary are intuitive, universal stomp-pedal concepts**. They're not legacy to be deprecated — they're the right shape for ~95% of button configs. The new cycle/timing model is a genuinely different *kind* of button (multi-state, press-duration-aware) and deserves its own mode rather than masquerading as a generalization of the simple cases.

**Replaced with:** `mode: "keytimes"` as a third primary mode alongside `toggle` and `momentary`. Toggle/momentary buttons keep their existing shape and dispatch path; only buttons that need cycling or long-press detection opt into the new mode and the new schema fields.

**Why the legacy `keytimes` + `states[]` fields on toggle/momentary are removed:** they were a half-baked version of what `mode: "keytimes"` now does properly. Keeping both would be two cycling mechanisms in the codebase, which smells. The user base is small enough that asking the handful of `keytimes`-using configs to be re-expressed in the new mode is reasonable — and the new mode is a strict superset of what the old fields could do, so nothing is lost.

### Why arrays for `down`/`up` even when single-message

Forward compatibility with #47 (multi-message per slot). Strict array form means no schema migration when #47 lands — only firmware logic changes (read all elements instead of index 0).

**Rejected:** polymorphic `Message | Message[]` shape. Easier for hand-authors, harder for the config editor and the schema validator. Strict arrays are the right trade for a mostly-tool-edited config.

### Why page-change cancels in-flight press

Alternatives:
- **(b)** Continue press; fire long/up events against the *original* page's bindings even though that page isn't displayed. Creates ghost events.
- **(c)** Rebind in-flight press to the new page's button at the same position. Incoherent — there's no guarantee the new page's button has the same press class defined.

**(a)** cancellation is the only sane default. (b) and (c) are documented in user-facing docs as "considered alternatives" so contributors with a concrete use case can advocate without re-discovering the trade-off.

---

## Phasing

This is too large for a single PR. The plan phases the work so each phase is independently shippable and reviewable.

| Phase | What | Status |
|---|---|---|
| 1: Foundation | `PressTracker` + `PressCycle` primitives + schema/validator for `mode: "keytimes"`. Pure-logic, fully unit-tested, no firmware integration. Ships nothing user-visible but lays the groundwork. | Detailed below |
| 2: Integration | `handle_switches()` adds a `mode == "keytimes"` branch consuming the new schema; color render rule + cycle state table wired in. v2.0 actually does the thing. | Outline only |
| 3: Polish | New example configs for keytimes mode; convert in-tree configs that used `keytimes`/`states` on non-keytimes modes; deprecation warning in validator (full removal deferred to v3.0); release notes and docs. | Outline only |

**Phase 1 is fully detailed below.** Phases 2 and 3 are outlined; each becomes its own plan when picked up.

There is no legacy-coexistence phase. Toggle, momentary, flash, and select keep their existing dispatch and schema; the `keytimes` mode is purely additive. The only removal is the legacy `keytimes`/`states` fields when used on non-keytimes-mode buttons — that's a hard rejection in the validator with a clear error message pointing users to the new mode.

---

## Phase 1: Foundation

**Goal:** Land the data-and-logic foundation for keytimes mode: `PressTracker` and `PressCycle` primitives (timing classification + cycle state), and the schema + validator changes so configs using `mode: "keytimes"` are parseable. No firmware integration yet — that's Phase 2.

**Files:**
- Modify: `firmware/dev/core/button.py` (add `PressTracker` and `PressCycle` classes — separate from `Switch` for testability)
- Modify: `firmware/dev/core/config.py` (validate `mode: "keytimes"` buttons; reject `keytimes`/`states` on other modes)
- Modify: `config.schema.json` (add `mode: "keytimes"` and the new fields; gate by mode)
- Test: `tests/test_press_tracker.py` (new)
- Test: `tests/test_press_cycle.py` (new)
- Test: `tests/test_press_tracker_cycle_integration.py` (new)
- Test: extend `tests/test_config.py` with keytimes-mode validation tests
- Reference: `tests/conftest.py` for any helpers

**Why separate classes from `Switch`:** `Switch` is a thin wrapper around `digitalio.DigitalInOut` and pull-up state. Timing logic is pure and best tested without any hardware mock. `PressTracker` consumes `(pressed: bool, now: float)` inputs and emits events. Compose: `Switch` produces edge-detected pressed/released, `PressTracker` adds timing classification, `PressCycle` tracks per-class cycle index.

### Task 1: PressTracker contract + failing test

**Files:**
- Create: `tests/test_press_tracker.py`

**Step 1: Write failing tests for the PressTracker contract**

Drop this into `tests/test_press_tracker.py`:

```python
"""Tests for press-timing classification."""
import pytest
from core.button import PressTracker


class TestPressTrackerIdle:
    def test_idle_no_events(self):
        tracker = PressTracker(threshold_ms=500)
        events = tracker.update(pressed=False, now=0.0)
        assert events == []


class TestPressTrackerShortPress:
    def test_press_emits_short_down(self):
        tracker = PressTracker(threshold_ms=500)
        events = tracker.update(pressed=True, now=0.0)
        assert events == ["short_down"]

    def test_release_before_threshold_emits_short_up(self):
        tracker = PressTracker(threshold_ms=500)
        tracker.update(pressed=True, now=0.0)
        events = tracker.update(pressed=False, now=0.2)
        assert events == ["short_up"]

    def test_hold_steady_no_events(self):
        tracker = PressTracker(threshold_ms=500)
        tracker.update(pressed=True, now=0.0)
        events = tracker.update(pressed=True, now=0.1)
        assert events == []


class TestPressTrackerLongPress:
    def test_threshold_emits_long_down(self):
        tracker = PressTracker(threshold_ms=500)
        tracker.update(pressed=True, now=0.0)
        events = tracker.update(pressed=True, now=0.5)
        assert events == ["long_down"]

    def test_long_down_fires_once(self):
        tracker = PressTracker(threshold_ms=500)
        tracker.update(pressed=True, now=0.0)
        tracker.update(pressed=True, now=0.5)
        events = tracker.update(pressed=True, now=1.0)
        assert events == []

    def test_release_after_threshold_emits_long_up(self):
        tracker = PressTracker(threshold_ms=500)
        tracker.update(pressed=True, now=0.0)
        tracker.update(pressed=True, now=0.5)
        events = tracker.update(pressed=False, now=0.7)
        assert events == ["long_up"]

    def test_release_after_threshold_does_not_emit_short_up(self):
        tracker = PressTracker(threshold_ms=500)
        tracker.update(pressed=True, now=0.0)
        tracker.update(pressed=True, now=0.5)
        events = tracker.update(pressed=False, now=0.7)
        assert "short_up" not in events


class TestPressTrackerSubsequentPresses:
    def test_two_short_presses_independent(self):
        tracker = PressTracker(threshold_ms=500)
        tracker.update(pressed=True, now=0.0)
        tracker.update(pressed=False, now=0.1)
        events = tracker.update(pressed=True, now=0.5)
        assert events == ["short_down"]

    def test_long_then_short(self):
        tracker = PressTracker(threshold_ms=500)
        tracker.update(pressed=True, now=0.0)
        tracker.update(pressed=True, now=0.5)
        tracker.update(pressed=False, now=0.7)
        events = tracker.update(pressed=True, now=1.0)
        assert events == ["short_down"]


class TestPressTrackerEdgeCases:
    def test_threshold_exactly(self):
        """Crossing the threshold exactly counts as long."""
        tracker = PressTracker(threshold_ms=500)
        tracker.update(pressed=True, now=0.0)
        events = tracker.update(pressed=True, now=0.5)
        assert events == ["long_down"]

    def test_immediate_long_press_from_initial_state(self):
        """First update with pressed=True at t=0 fires short_down; later update past threshold fires long_down."""
        tracker = PressTracker(threshold_ms=500)
        events_t0 = tracker.update(pressed=True, now=0.0)
        events_t1 = tracker.update(pressed=True, now=0.6)
        assert events_t0 == ["short_down"]
        assert events_t1 == ["long_down"]

    def test_release_with_no_prior_press(self):
        """Defensive: spurious release without preceding press emits nothing."""
        tracker = PressTracker(threshold_ms=500)
        events = tracker.update(pressed=False, now=0.0)
        assert events == []
```

**Step 2: Run tests, verify they all fail**

```bash
cd firmware/dev && python -m pytest ../../tests/test_press_tracker.py -v
```

Expected: ImportError or "PressTracker not defined" for every test.

**Step 3: Commit failing tests**

```bash
git add tests/test_press_tracker.py
git commit -m "Add failing tests for PressTracker timing classification (#48)"
```

---

### Task 2: Minimal PressTracker implementation

**Files:**
- Modify: `firmware/dev/core/button.py` (append `PressTracker` class)

**Step 1: Write the minimal implementation**

Append to `firmware/dev/core/button.py`:

```python
class PressTracker:
    """Classifies button press events into short/long timing slots.

    Consumes (pressed, now) on every poll and returns a list of timing events
    that fired during the transition. Designed to compose with Switch — the
    caller passes Switch.pressed and time.monotonic() each loop.

    Threshold defines the boundary between short and long presses. A release
    before threshold emits short_up; a release after emits long_up. The
    short_down event fires immediately on every physical press; long_down
    fires once when threshold is reached while still held.
    """

    def __init__(self, threshold_ms):
        self.threshold_s = threshold_ms / 1000.0
        self._pressed = False
        self._down_at = None
        self._long_fired = False

    def update(self, pressed, now):
        """Process one poll. Returns a list of event names that fired.

        Event names: "short_down", "short_up", "long_down", "long_up".
        Multiple events can fire in one update (e.g. long_down arriving during
        a steady hold). Returned list preserves firing order.
        """
        events = []

        if pressed and not self._pressed:
            self._pressed = True
            self._down_at = now
            self._long_fired = False
            events.append("short_down")
        elif pressed and self._pressed:
            if not self._long_fired and (now - self._down_at) >= self.threshold_s:
                self._long_fired = True
                events.append("long_down")
        elif not pressed and self._pressed:
            self._pressed = False
            if self._long_fired:
                events.append("long_up")
            else:
                events.append("short_up")
            self._down_at = None
            self._long_fired = False

        return events
```

**Step 2: Run tests, verify they pass**

```bash
cd firmware/dev && python -m pytest ../../tests/test_press_tracker.py -v
```

Expected: all tests pass.

**Step 3: Commit the implementation**

```bash
git add firmware/dev/core/button.py
git commit -m "Implement PressTracker class for short/long press classification (#48)"
```

---

### Task 3: Add per-press-class state for multi-press cycle support

PressTracker only classifies a single press. The cycle-state (which entry to fire from) is separate concern — a `PressCycle` class.

**Files:**
- Create: tests in `tests/test_press_cycle.py`
- Modify: `firmware/dev/core/button.py` (add `PressCycle` class)

**Step 1: Write failing tests**

```python
"""Tests for press-cycle state (independent counters per short/long class)."""
from core.button import PressCycle


class TestPressCycleAdvancement:
    def test_initial_index_zero(self):
        cycle = PressCycle(length=3)
        assert cycle.index == 0

    def test_advance_increments(self):
        cycle = PressCycle(length=3)
        cycle.advance()
        assert cycle.index == 1

    def test_advance_wraps(self):
        cycle = PressCycle(length=3)
        cycle.advance()
        cycle.advance()
        cycle.advance()
        assert cycle.index == 0

    def test_length_one_advance_stays_at_zero(self):
        cycle = PressCycle(length=1)
        cycle.advance()
        assert cycle.index == 0

    def test_length_zero_no_advance(self):
        """Zero-length cycle (no events defined) doesn't change index."""
        cycle = PressCycle(length=0)
        cycle.advance()
        assert cycle.index == 0

    def test_reset(self):
        cycle = PressCycle(length=3)
        cycle.advance()
        cycle.advance()
        cycle.reset()
        assert cycle.index == 0
```

**Step 2: Run tests, verify they fail**

```bash
cd firmware/dev && python -m pytest ../../tests/test_press_cycle.py -v
```

Expected: ImportError or "PressCycle not defined."

**Step 3: Commit failing tests**

```bash
git add tests/test_press_cycle.py
git commit -m "Add failing tests for PressCycle state (#48)"
```

**Step 4: Implement PressCycle**

Append to `firmware/dev/core/button.py`:

```python
class PressCycle:
    """Tracks the current entry index for one timing class (short or long).

    Independent of PressTracker — a button has two PressCycles (short, long)
    each managing its own index. Advanced once per physical press in which
    at least one event from this class fired.
    """

    def __init__(self, length):
        self.length = length
        self.index = 0

    def advance(self):
        """Advance index by 1, wrapping at length. No-op when length <= 0."""
        if self.length > 0:
            self.index = (self.index + 1) % self.length

    def reset(self):
        """Reset index to 0 (e.g. on power cycle or config reload)."""
        self.index = 0
```

**Step 5: Run tests, verify they pass**

```bash
cd firmware/dev && python -m pytest ../../tests/test_press_cycle.py -v
```

Expected: all pass.

**Step 6: Commit**

```bash
git add firmware/dev/core/button.py
git commit -m "Implement PressCycle for per-class cycle state (#48)"
```

---

### Task 4: Composition test — PressTracker + PressCycle end-to-end

Verify the two classes compose as the design intends: feed timing events from PressTracker into the correct PressCycle's advancement, and trace the user's real-world reverb+shimmer scenario.

**Files:**
- Create: `tests/test_press_tracker_cycle_integration.py`

**Step 1: Write failing test for the scenario**

```python
"""Integration: PressTracker + PressCycle traces the reverb+shimmer scenario.

Replicates the user's OEM config:
- short_up_1: reverb on
- long_down_1: shimmer on
- short_up_2: reverb off
- long_down_2: shimmer off
"""
from core.button import PressTracker, PressCycle


def _advance_cycles(events, short_cycle, long_cycle):
    """Advance the relevant cycle at most once per call, per design rule."""
    fired_short = any(e in ("short_down", "short_up") for e in events)
    fired_long = any(e in ("long_down", "long_up") for e in events)
    if fired_short:
        short_cycle.advance()
    if fired_long:
        long_cycle.advance()


def test_reverb_shimmer_sequence():
    tracker = PressTracker(threshold_ms=500)
    short = PressCycle(length=2)
    long_ = PressCycle(length=2)

    # Initial state
    assert short.index == 0
    assert long_.index == 0

    # 1. Short tap — reverb on
    tracker.update(pressed=True, now=0.0)
    events = tracker.update(pressed=False, now=0.1)
    assert "short_up" in events
    _advance_cycles(events, short, long_)
    assert short.index == 1
    assert long_.index == 0

    # 2. Long hold — shimmer on
    tracker.update(pressed=True, now=1.0)
    events_threshold = tracker.update(pressed=True, now=1.5)
    events_release = tracker.update(pressed=False, now=1.7)
    assert "long_down" in events_threshold
    assert "long_up" in events_release
    _advance_cycles(events_threshold + events_release, short, long_)
    assert short.index == 1   # unchanged — no short event fired
    assert long_.index == 1   # advanced

    # 3. Long hold — shimmer off
    tracker.update(pressed=True, now=2.0)
    events_threshold = tracker.update(pressed=True, now=2.5)
    events_release = tracker.update(pressed=False, now=2.7)
    _advance_cycles(events_threshold + events_release, short, long_)
    assert short.index == 1
    assert long_.index == 0   # wrapped

    # 4. Short tap — reverb off
    tracker.update(pressed=True, now=3.0)
    events = tracker.update(pressed=False, now=3.1)
    _advance_cycles(events, short, long_)
    assert short.index == 0   # wrapped
    assert long_.index == 0
```

**Step 2: Run, verify it passes**

```bash
cd firmware/dev && python -m pytest ../../tests/test_press_tracker_cycle_integration.py -v
```

Expected: passes (both classes are now implemented).

**Step 3: Commit**

```bash
git add tests/test_press_tracker_cycle_integration.py
git commit -m "Add integration test for PressTracker + PressCycle (#48)"
```

---

### Task 5: Phase 1 verification & PR

**Step 1: Run full test suite to verify no regressions**

```bash
cd firmware/dev && python -m pytest ../../tests/ -v
```

Expected: all existing tests still pass; three new test files pass.

**Step 2: Push branch and open PR**

```bash
git push -u origin <branch-name>
gh pr create --title "feat(#48): foundation — PressTracker, PressCycle, keytimes-mode validator (phase 1 of 3)" --body "$(cat <<'EOF'
First phase of #48 (press timings). Lands the data-and-logic foundation for `mode: "keytimes"` — primitives, schema, validator. No firmware integration yet.

## What's added
- `PressTracker` — classifies a physical press into `short_down`/`short_up`/`long_down`/`long_up` events based on a configurable threshold
- `PressCycle` — independent index counter for one timing class, with wrap-around and reset
- `mode: "keytimes"` recognized by validator; `short[]`/`long[]`/`long_press_threshold_ms` parsed and validated on keytimes-mode buttons
- Validator rejects legacy `keytimes`/`states` on non-keytimes-mode buttons with a helpful error pointing to the new mode
- Unit tests for primitives + integration test tracing the reverb+shimmer scenario + validator tests

## What's not changed yet
- Dispatch (`code.py`) — phase 2 wires the new schema into `handle_switches()`
- Color rendering and cycle state table — phase 2
- Example configs — phase 3

See `docs/plans/2026-05-13-issue-48-press-timings.md` for the full design and phasing.

## Test plan
- [x] `pytest tests/test_press_tracker.py` passes
- [x] `pytest tests/test_press_cycle.py` passes
- [x] `pytest tests/test_press_tracker_cycle_integration.py` passes
- [x] `pytest tests/test_config.py` passes including new keytimes-mode tests
- [x] Existing test suite unaffected
EOF
)"
```

---

## Phase 2 (Outline): Integration

Goal: firmware actually *uses* the new schema for `mode: "keytimes"` buttons. Other modes' dispatch paths are completely untouched.

- **Loop hook:** `code.py`'s `handle_switches()` adds a new branch when `mode == "keytimes"`. For those buttons, the loop polls `pressed` + `time.monotonic()` and feeds them through one `PressTracker` per keytimes button (allocated at startup, only for keytimes-mode buttons — others don't need timing classification).
- **Per-button dispatch:** For each event in the returned list, look up the matching slot in the new schema (e.g. `short[short_idx].down`) and dispatch its `Message[]` (initially just `[0]`, full iteration deferred to #47). After dispatch, advance the relevant cycle at most once per press.
- **No legacy fallback path:** the existing dispatch branches for `cc`/`pc`/`note`/`hid` × `toggle`/`momentary`/`flash`/`select` are unchanged. The keytimes branch is purely additive.
- **Tests:** dispatch table for each (event, message-type) combo; integration test for the reverb+shimmer scenario at the firmware level (mocked MIDI bus); verification that non-keytimes-mode buttons are completely unaffected by the new code path.

### Color Rendering & Cycle State Table (within Phase 2)

Per-button cycle state lives in a structure designed to extend to per-page for #15. LED renders per the two-layer rule.

- **State table:** `cycle_state[button_idx] = {short_idx, long_idx, short_color, long_color}`. When pages land (#15), key on `(page_id, button_idx)`.
- **Color inherit:** When an entry has no `color` field, the layer's stored color persists. `"off"` explicitly clears it.
- **Render function:** `compute_led_color(short_color, long_color) → rgb` per the kill-switch rule.
- **Tests:** color trace for the reverb+shimmer example (`[white, blue, off, blue, white]`); inherit semantics; `"off"` asymmetry.

## Phase 3 (Outline): Example Configs & Legacy Cleanup

Goal: ship example configs for `mode: "keytimes"`; remove the legacy `keytimes`/`states` fields from non-keytimes example configs (cleaning up in-tree configs that the validator now rejects).

### New example configs

- Add `config-example-keytimes-mode.json` showcasing `mode: "keytimes"`: a reverb+shimmer pattern, a multi-state cycle (3 short × 2 long Lead button from the asymmetry rationale), and a long-press-only button. Include `long_press_threshold_ms` override examples.
- Update `config-example-all-types.json` to demonstrate `mode: "keytimes"` alongside existing modes — showing the three primary modes side-by-side.

### Cleanup of legacy in-tree configs

The existing `config-example-keytimes.json` and `config-example-mini6-keytimes.json` files use the old `keytimes: N` + `states[]` shape on `mode: "toggle"` buttons. Once Phase 2's validator rejects that combination, those configs won't load. Two options:

- **Rewrite them as `mode: "keytimes"` examples** — preferred. Preserves the demo value and shows the new shape.
- **Delete them entirely** — acceptable if the new `config-example-keytimes-mode.json` covers the same ground.

Check device-default configs (`config-mini6.json`, `config-nano4.json`, etc.) for any `keytimes`/`states` usage and clear them; default configs shouldn't depend on the deprecated combination.

### User-facing release notes

For v2.0 release notes / changelog (these are for users, not contributors):

- **New:** `mode: "keytimes"` adds long-press detection and rich multi-state cycling. See `config-example-keytimes-mode.json` for usage.
- **Breaking:** the `keytimes: N` and `states[]` fields no longer work on `mode: "toggle"` or `mode: "momentary"` buttons. If you used them, switch the button to `mode: "keytimes"` and re-express the cycle in the new shape. The new mode is a strict superset and can do everything the old fields could, plus long-press.
- Toggle, momentary, flash, and select modes are otherwise unchanged. Plain stomp configs continue to work without modification.

### Tasks

- Write new keytimes-mode example configs.
- Rewrite or delete legacy in-tree configs that use `keytimes`/`states` on non-keytimes modes.
- Update `AGENTS.md` and any user-facing config docs with the three-mode framing and a "which mode should I use?" decision guide.
- Add v2.0 release notes to the project README or changelog.

No automatic migration code is shipped. The user base is small enough (and the affected subset — anyone using `keytimes` + `states` — even smaller) that a clean break with clear release notes is the right trade.

---

## Open Items for Future Plans

These were identified during design but deferred:

- **#125 (select-mode + keytimes compatibility):** select mode (#43) and keytimes mode are mutually exclusive in v2.0 — they're separate `mode` values, so a button is one or the other. Some users may want both behaviors (group-radio selection AND long-press), so #125 tracks a future design for combining them. Not blocking #48.
- **#15 (pages):** when pages land, cycle state must key on `(page_id, button_idx)`. The phase 4 table is designed for this — adding the page dimension is a refactor of one key access, not a re-architecture.
- **#47 (multi-message):** phase 3's dispatcher reads `Message[]` but only processes index 0. When #47 lands, replace the index-0 read with iteration. No schema migration needed.
- **#123 (CC ramp):** independent feature. Lives outside the short/long cycle model; consumes the long-press threshold to start the ramp.
- **`hold` slot (repeating-while-held):** schema reserved, no implementation. Add when a concrete use case arises.
- **Page-change-mid-press alternatives (b) and (c):** documented as rejected; revisit if a user-reported use case justifies one.
- **Color priority inversion:** YAGNI; one-line opt-in flag if requested.

---

## Concerns & Risks

- **CircuitPython performance:** the polling loop must call `time.monotonic()` for every switch every iteration. On the std10 (10 switches) this is 10 timestamp reads per poll — negligible, but worth verifying the loop's overall frequency doesn't degrade. Bench on hardware after phase 3 lands.
- **`time.monotonic()` precision on CircuitPython:** documented as second-precision on some boards. Verify on RP2040 — if precision is too coarse for 500ms thresholds, consider `time.monotonic_ns()` instead.
- **Per-button PressTracker allocation:** STD10 has up to 10 footswitches → 10 PressTracker instances. Memory is trivial but should be confirmed within CircuitPython heap limits on the smallest target (DUO2, ONE1).
- **CircuitPython 7.x missing `str` methods:** existing project gotcha. None of the new code uses `isalnum()`/`isalpha()`/`isdigit()` — it deals only in numbers and booleans. No exposure.
- **Test-time mocking of `time.monotonic`:** existing `tests/conftest.py` may have helpers; if not, the tests pass an explicit `now` argument so no mock is needed.
