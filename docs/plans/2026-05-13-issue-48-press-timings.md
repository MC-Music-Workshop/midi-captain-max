# Press Timings & Long-Press Implementation Plan (#48)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add OEM-parity press-timing support to footswitches — short/long press detection with independent message cycles, replacing the current `keytimes`/`states[]` shape with a cleaner two-cycle model.

**Architecture:** Two independent cycles per button (`short`, `long`), each an array of entries with optional `down`/`up`/`color` sub-fields. A polling-loop threshold timer in the firmware detects when a held button transitions from "short" to "long" classification. Cycle state lives in a per-page table in RAM (per-page model is forward-compatible with #15). The schema reserves array-of-messages per slot (single-element today, multi-element later per #47).

**Tech Stack:** CircuitPython firmware (Python), pytest for firmware tests, JSON schema for config validation.

**Resolves:** #48 (this issue), #73 (external-contributor parity request), partially feeds #15 (pages) and #47 (multi-message).
**Closes:** #14 (already closed as duplicate of #73).
**Forward-links:** #15 (pages), #47 (multi-message per slot), #123 (CC ramp).

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

Each button has **two independent cycles**: `short` and `long`. Each is an array of entries. Each entry has optional `down`, `up`, and `color` sub-fields. The down/up of the same entry are paired by physical press (same as OEM's `short_dwN`/`short_upN` pairing by N).

**Advancement rule:** Per cycle, per physical press — advance by 1 if ≥1 of that cycle's events fired during the press; else don't advance.

So a short tap with both `short_down` and `short_up` defined → both fire, short cycle advances **by 1** (not 2). A long press with both `short_down` and `long_down` defined → both fire (different cycles), each advances by 1.

### Threshold

- `long_press_threshold_ms` is a top-level config field. Default **500ms**.
- Each button may set its own `long_press_threshold_ms` override.
- Resolution: button override if set, else global, else 500.

### Color Render Rule

Each cycle's current entry carries an optional `color`. The two layers combine as:

```
if short.color == "off":     LED = off       (kill switch — short "off" overrides all)
elif long.color is set:      LED = long      (decoration over primary)
elif short.color is set:     LED = short
else:                        LED = off
```

Within a cycle, an entry with no `color` field **inherits** the previous entry's color. An explicit `"off"` is distinct from unset.

The asymmetry (`"off"` on short kills the LED but `"off"` on long is just "no decoration") matches the physical pedalboard metaphor: short is the primary indicator, long is a decoration painted over it; with no primary, there's nothing to decorate.

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

```json
{
  "label": "VERB",
  "color": "blue",
  "long_press_threshold_ms": 500,
  "short": [
    { "down": [{ "type": "cc", "cc": 20, "value": 127 }], "color": "white" },
    { "down": [{ "type": "cc", "cc": 20, "value": 0   }], "color": "off"   }
  ],
  "long": [
    { "down": [{ "type": "cc", "cc": 21, "value": 127 }], "color": "blue"  },
    { "down": [{ "type": "cc", "cc": 21, "value": 0   }], "color": "white" }
  ]
}
```

Each sub-action (`down`, `up`) is an **array** of message objects, even when there's only one. This reserves the shape for #47 (multi-message per slot) without future migration. Initial firmware reads index `[0]` only; later firmware iterates the full list.

Message objects use the existing `type`-discriminated shape (`{type: "cc", cc, value}`, `{type: "pc", program}`, `{type: "note", note, velocity}`, `{type: "hid", action, key, modifier, delay_ms}`). This converges with the unified-message-types plan (`docs/plans/2026-03-01-unified-message-types.md`).

---

## Design Rationale & Alternatives Considered

This section preserves the *why* behind the choices so future contributors don't re-litigate them.

### Why two independent cycles instead of one shared

A user's real OEM config: short-press 1 = reverb on, short-press 2 = reverb off, long-press 1 = shimmer on, long-press 2 = shimmer off. This only works if short and long maintain independent counters — otherwise a hold in the middle of a sequence would scramble the short cycle.

OEM does the same: `short_upX` and `longX` increment their X separately.

**Rejected:** one shared cycle index across both short and long. It collapses the two-effect-per-button pattern into a single sequence, which is strictly less expressive than OEM and breaks the reverb+shimmer scenario.

### Why pair `down`/`up` within an entry instead of independent timing sequences

OEM pairs `short_dwN` and `short_upN` by N — both reference "the Nth short press." Within a single physical press, the down and up events are bookends of the same event, so they must use the same cycle index.

**Rejected:** separate `short_down: [...]`, `short_up: [...]` arrays with independent counters. This would mean down and up could desynchronize, which isn't physically possible (every down has a matching up). Pairing inside one entry object is correct.

**Rejected:** wrapper renames `short_press_cycle`/`long_press_cycle`, nested `cycles.short`/`cycles.long`, per-entry `n` field for explicit indexing. The schema as proposed already matches OEM's pairing-by-index semantics; further naming changes added clutter without clarity. The doc and examples carry the burden of teaching the pairing.

### Why "long modifies short" for color, with `"off"`-on-short as kill switch

Pedalboard mental model: the short cycle is the *primary* effect indicator. The long cycle is a *decoration* (secondary effect) painted on top. When the primary is off, the LED is dark — there's nothing for the decoration to attach to.

Concretely, this preserves the user's traced expectation: with reverb (short=white) + shimmer (long=blue), the LED is blue while both are on. Hit short again to turn reverb off (short=`off`); LED goes dark even though shimmer is still on, because there's no primary effect to color.

**Rejected:** symmetric override ("long always wins when set"). Loses the kill-switch semantic and surprises users who turn off the primary effect.

**Rejected:** RGB blending of short + long colors. Cute but unpredictable and impossible to reason about during a gig.

**Deferred:** opt-in inversion flag `color_priority: "short" | "long"`. YAGNI — no concrete use case. If one surfaces, easy to add as a button-level flag without migration.

### Why `hold` is reserved for the repeating flavor only

"Continuous on/off while held" (CC-on at threshold, CC-off at release) is already expressible via `long_down` (on) + `long_up` (off). No new slot needed. Reserving `hold` exclusively for the repeating-while-held flavor avoids overloading the term.

CC ramp (continuous interpolation while held) is filed separately as #123 — different enough to merit its own field, not just a `hold` variant.

### Why `states[]` and `keytimes` count are removed

The current shape locks each button to one `cc` channel and message type (`cc_on`/`cc_off` values vary per state). Adding long-press would force each state to carry multiple message variants and possibly different message types — the flat shape doesn't compose.

**Replaced with:** cycle arrays where length *is* the count, each entry can carry any message type, and `down`/`up`/`color` are first-class per-entry fields.

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
| 1 | Switch timing infrastructure: timer/threshold detection in `Switch` class. Pure-test, no config changes. | Detailed below |
| 2 | Schema + validator: parse new `short`/`long`/`long_press_threshold_ms` fields. New code doesn't yet *use* them. | Outline only |
| 3 | New dispatch core: `handle_switches()` consumes the new schema for buttons that declare `short`/`long`. Old buttons keep working via the existing dispatch path. | Outline only |
| 4 | Color render rule + cycle state table (forward-compatible with per-page). | Outline only |
| 5 | Migrate all example configs to the new shape. Deprecate old shape via validator warning. | Outline only |
| 6 | Remove old shape entirely (post-#47, post-#15). | Future plan |

**Phase 1 is fully detailed below.** Phases 2–5 are outlined; each becomes its own plan when it gets picked up. This keeps the plan document focused on actionable work without ballooning to thousands of lines.

---

## Phase 1: Switch Timing Infrastructure

**Goal:** Extend the `Switch` class so it produces timing-classified events (`short_down`, `short_up`, `long_down`, `long_up`) based on observed press lifecycle, with no impact on existing dispatch.

**Files:**
- Modify: `firmware/dev/core/button.py` (add `PressTracker` class — separate from `Switch` for testability)
- Test: `tests/test_press_tracker.py` (new file)
- Reference: `tests/conftest.py` for time-mocking patterns

**Why a separate class instead of bolting onto `Switch`:** `Switch` is a thin wrapper around `digitalio.DigitalInOut` and pull-up state. Timing logic is pure and best tested without any hardware mock. `PressTracker` consumes `(pressed: bool, now: float)` inputs and emits events. Compose: `Switch` produces edge-detected pressed/released, `PressTracker` adds timing classification.

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
gh pr create --title "feat(#48): add PressTracker and PressCycle primitives (phase 1 of 5)" --body "$(cat <<'EOF'
First phase of #48 (press timings). Adds timing-classification primitives in `core/button.py` with no impact on existing dispatch — these are building blocks for phases 2–5.

## What's added
- `PressTracker` — classifies a physical press into `short_down`/`short_up`/`long_down`/`long_up` events based on a configurable threshold
- `PressCycle` — independent index counter for one timing class, with wrap-around and reset
- Unit tests for each + integration test tracing the reverb+shimmer scenario

## What's not changed
- Schema (`config.schema.json`) — phase 2
- Dispatch (`code.py`) — phase 3
- Color rendering — phase 4
- Example configs — phase 5

See `docs/plans/2026-05-13-issue-48-press-timings.md` for the full design and phasing.

## Test plan
- [x] `pytest tests/test_press_tracker.py` passes
- [x] `pytest tests/test_press_cycle.py` passes
- [x] `pytest tests/test_press_tracker_cycle_integration.py` passes
- [x] Existing test suite unaffected
EOF
)"
```

---

## Phase 2 (Outline): Schema & Validator

Goal: parse new fields without consuming them yet. Lays groundwork for phase 3.

- **Schema:** Extend `config.schema.json` with the new top-level field `long_press_threshold_ms` (number, default 500) and per-button `short`, `long`, `hold` fields. Reserve `hold` as schema-only (no validator support yet).
- **Validator:** `validate_button` in `firmware/dev/core/config.py` learns to parse `short[]` and `long[]` as lists of entries, each with optional `down: Message[]`, `up: Message[]`, `color: string`. Each `Message` validated by type (`cc`, `pc`, `note`, `hid`, `pc_inc`, `pc_dec`). `long_press_threshold_ms` accepted at both top level and per-button.
- **Mutual exclusion:** A button cannot have BOTH the new shape (`short`/`long`) AND the legacy shape (`cc` + `cc_on`/`cc_off`/`keytimes`/`states`). Validator rejects, falling back to legacy with a warning.
- **Tests:** schema parses, defaults applied, threshold resolution (button override > global > 500), invalid shapes rejected gracefully.

Estimated effort: ~12 tasks of TDD-pace.

## Phase 3 (Outline): Dispatch Core

Goal: firmware actually *uses* the new schema for buttons that opt in. Legacy buttons unchanged.

- **Loop hook:** `code.py`'s `handle_switches()` polls each switch's `pressed` + `time.monotonic()` and feeds them through one `PressTracker` per button (allocated at startup). Events drive a per-button dispatcher.
- **Per-button dispatch:** For each event in the returned list, look up the matching slot in the new schema (e.g. `short[short_idx].down`) and dispatch its `Message[]` (initially just `[0]`, full iteration deferred to #47). After dispatch, advance the relevant cycle at most once per press.
- **Co-existence:** Buttons with legacy fields (`cc`, `keytimes`, etc.) skip the new dispatcher and use existing logic. Decision deferred to phase 5.
- **Tests:** dispatch table for each (event, message-type) combo; integration test for the reverb+shimmer scenario at the firmware level (mocked MIDI bus).

## Phase 4 (Outline): Color Rendering & Cycle State Table

Goal: per-button cycle state lives in a structure designed to extend to per-page for #15. LED renders per the two-layer rule.

- **State table:** `cycle_state[button_idx] = {short_idx, long_idx, short_color, long_color}`. When pages land (#15), key on `(page_id, button_idx)`.
- **Color inherit:** When an entry has no `color` field, the layer's stored color persists. `"off"` explicitly clears it.
- **Render function:** `compute_led_color(short_color, long_color) → rgb` per the kill-switch rule.
- **Tests:** color trace for the reverb+shimmer example (`[white, blue, off, blue, white]`); inherit semantics; `"off"` asymmetry.

## Phase 5 (Outline): Example Config Migration & Deprecation

Goal: convert in-tree example configs to the new shape; warn on legacy shape.

- **Migrate:** `config-example-keytimes.json`, `config-example-mini6-keytimes.json`, `config-example-all-types.json`, plus the device-default configs if they use keytimes/states.
- **Migration script:** one-shot Python script in `firmware/dev/scripts/migrate_legacy_keytimes.py` that converts a legacy config to the new shape. Run once, commit results, archive the script under `docs/migrations/`.
- **Deprecation warning:** validator prints a warning when legacy `keytimes`/`states` is detected. Schema can also flag deprecated.
- **Docs:** update `AGENTS.md` and any user-facing config docs.

Final removal of legacy shape: separate plan, deferred until #47 and #15 are landed (since both interact with cycle state).

---

## Open Items for Future Plans

These were identified during design but deferred:

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
