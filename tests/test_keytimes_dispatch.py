"""Tests for dispatch_keytimes_events (#48).

The dispatcher is a pure function that takes events from PressTracker, a
KeytimesButtonState, and a button config, then:
  - calls a message_callback for each Message in the matching cycle entry's slot
  - updates state's inherited color/dim/label from the entry
  - advances the relevant PressCycle(s) on press-end events
"""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.button import KeytimesButtonState, dispatch_keytimes_events


def _msg_collector():
    """Helper: returns (callback, captured_list)."""
    captured = []
    return captured.append, captured


def _make_state(short_len, long_len, threshold_ms=500):
    return KeytimesButtonState(threshold_ms=threshold_ms, short_length=short_len, long_length=long_len)


def CC(cc, value):
    return {"type": "cc", "cc": cc, "value": value}


class TestDispatchBasic:
    def test_no_events_no_messages(self):
        state = _make_state(1, 1)
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes", "short": [{"down": [CC(20, 127)]}]}
        dispatch_keytimes_events([], state, cfg, cb)
        assert captured == []
        assert state.short_cycle.index == 0

    def test_short_down_fires_message(self):
        state = _make_state(1, 1)
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes", "short": [{"down": [CC(20, 127)]}]}
        dispatch_keytimes_events(["short_down"], state, cfg, cb)
        assert captured == [CC(20, 127)]

    def test_short_up_fires_up_message(self):
        state = _make_state(1, 1)
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes", "short": [{"up": [CC(20, 0)]}]}
        dispatch_keytimes_events(["short_up"], state, cfg, cb)
        assert captured == [CC(20, 0)]

    def test_long_down_fires_long_message(self):
        state = _make_state(1, 1)
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes", "long": [{"down": [CC(21, 127)]}]}
        dispatch_keytimes_events(["long_down"], state, cfg, cb)
        assert captured == [CC(21, 127)]

    def test_unknown_event_ignored(self):
        state = _make_state(1, 1)
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes", "short": [{"down": [CC(20, 127)]}]}
        dispatch_keytimes_events(["bogus"], state, cfg, cb)
        assert captured == []


class TestDispatchCycleAdvancement:
    def test_short_tap_advances_short_cycle(self):
        state = _make_state(2, 1)
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"down": [CC(20, 64)]}, {"down": [CC(20, 127)]}]}
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert state.short_cycle.index == 1
        # First press fires entry[0]'s down message.
        assert captured == [CC(20, 64)]

    def test_next_short_tap_fires_next_entry(self):
        state = _make_state(2, 1)
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"down": [CC(20, 64)]}, {"down": [CC(20, 127)]}]}
        # First tap
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        # Second tap should fire entry[1].down
        captured.clear()
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert captured == [CC(20, 127)]
        assert state.short_cycle.index == 0  # wrapped

    def test_long_press_advances_long_cycle_when_short_down_undefined(self):
        # short_down doesn't fire (no entries on the short side? Actually short_down ALWAYS fires
        # from the tracker — but if short cycle has 0 entries, advance is a no-op).
        state = _make_state(0, 2)
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes",
               "long": [{"down": [CC(21, 127)]}, {"down": [CC(21, 0)]}]}
        dispatch_keytimes_events(["short_down", "long_down", "long_up"], state, cfg, cb)
        # short_cycle length is 0, advance is no-op
        assert state.short_cycle.index == 0
        # long_cycle advances
        assert state.long_cycle.index == 1
        # First long press fires long entry[0].down
        assert captured == [CC(21, 127)]

    def test_long_press_advances_both_when_short_down_has_entries(self):
        state = _make_state(2, 2)
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"down": [CC(20, 64)]}, {"down": [CC(20, 127)]}],
               "long":  [{"down": [CC(21, 127)]}, {"down": [CC(21, 0)]}]}
        # Full long press fires short_down, long_down, long_up
        dispatch_keytimes_events(["short_down", "long_down", "long_up"], state, cfg, cb)
        # Both cycles advance: short_down fired -> short advances; long_down/long_up fired -> long advances
        assert state.short_cycle.index == 1
        assert state.long_cycle.index == 1
        # Messages dispatched in order
        assert captured == [CC(20, 64), CC(21, 127)]  # no long_up message defined in cfg

    def test_advance_only_once_per_press_with_both_down_and_up_short(self):
        state = _make_state(3, 0)
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [
                   {"down": [CC(20, 1)], "up": [CC(20, 2)]},
                   {"down": [CC(20, 3)], "up": [CC(20, 4)]},
                   {"down": [CC(20, 5)], "up": [CC(20, 6)]},
               ]}
        # short_down AND short_up both fire — short cycle should advance ONCE
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert state.short_cycle.index == 1  # advanced by 1, not 2
        assert captured == [CC(20, 1), CC(20, 2)]  # both entry[0]'s down and up fired


class TestDispatchColorState:
    def test_color_updated_from_entry(self):
        state = _make_state(2, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"down": [CC(20, 64)], "color": "blue"},
                         {"down": [CC(20, 127)], "color": "cyan"}]}
        dispatch_keytimes_events(["short_down"], state, cfg, cb)
        assert state.short_color == "blue"

    def test_color_clears_when_entry_has_no_color(self):
        # An entry with no "color" field clears the layer's color so the render
        # falls back to the button-level color. "(inherit)" means "no override",
        # not "carry forward the previous entry's color".
        state = _make_state(2, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"down": [CC(20, 64)], "color": "blue"},
                         {"down": [CC(20, 127)]}]}  # no color on entry 1
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        # After short_up, cycle advanced to index 1. The next press will hit entry 1.
        # state.short_color still reflects entry 0 (the one that just fired).
        assert state.short_color == "blue"
        # Next press hits entry 1 — no color → clear so render falls back to button color.
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert state.short_color is None

    def test_render_state_unchanged_when_slot_has_no_messages(self):
        # Strict rule: short_down with no down messages does nothing — neither MIDI
        # nor render. This is the fix for the "short_down flash" during long presses.
        state = _make_state(1, 0)
        state.short_color = "white"  # simulate prior state from a previous press
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"up": [CC(20, 127)], "color": "off"}]}  # only up has content
        dispatch_keytimes_events(["short_down"], state, cfg, cb)
        assert captured == []
        assert state.short_color == "white"  # unchanged — slot was empty

    def test_long_press_does_not_advance_short_cycle_when_short_down_empty(self):
        # Regression: previously, short_down fired during a long press would mark
        # _fired_short=True and the short cycle would advance at long_up, even
        # though no short MIDI fired. Now: short_down with empty slot is silent
        # on every axis (MIDI, render, cycle) so the short cycle stays put.
        state = _make_state(2, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"up": [CC(20, 127)]}, {"up": [CC(20, 0)]}],  # only up slots
               "long":  [{"down": [CC(21, 127)]}]}
        # One short tap to advance short cycle to index 1.
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert state.short_cycle.index == 1
        # Now do a long press. Short cycle should NOT advance.
        dispatch_keytimes_events(["short_down", "long_down", "long_up"], state, cfg, cb)
        assert state.short_cycle.index == 1   # stays — short_down had no content
        assert state.long_cycle.index == 0    # advanced and wrapped (len=1)

    def test_off_does_not_persist_through_inherit_entry(self):
        # Regression: previously [inherit, off] would stick at "off" after the
        # first wrap because the inherit entry left short_color unchanged.
        state = _make_state(2, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"down": [CC(20, 64)]},                      # inherit
                         {"down": [CC(20, 0)], "color": "off"}]}
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert state.short_color is None  # entry 0 inherit
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert state.short_color == "off"  # entry 1 kill
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert state.short_color is None  # wrap to entry 0 — kill cleared

    def test_long_color_updates_on_long_event(self):
        state = _make_state(1, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes",
               "long": [{"down": [CC(21, 127)], "color": "red"}]}
        dispatch_keytimes_events(["long_down"], state, cfg, cb)
        assert state.long_color == "red"
        assert state.short_color is None

    def test_dim_true_set_on_entry(self):
        state = _make_state(1, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"down": [CC(20, 64)], "color": "blue", "dim": True}]}
        dispatch_keytimes_events(["short_down"], state, cfg, cb)
        assert state.short_dim is True

    def test_dim_resets_when_next_entry_has_no_dim(self):
        state = _make_state(2, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"down": [CC(20, 64)], "color": "blue", "dim": True},
                         {"down": [CC(20, 127)], "color": "blue"}]}
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert state.short_dim is True  # entry 0 had dim
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert state.short_dim is False  # entry 1 has no dim — resets

    def test_label_updated_from_entry(self):
        state = _make_state(1, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"down": [CC(20, 64)], "label": "VERB+"}]}
        dispatch_keytimes_events(["short_down"], state, cfg, cb)
        assert state.short_label == "VERB+"


class TestLastFired:
    """state.last_fired drives which timing class owns the LED + label render.

    Regression for the beta.9 "long label always sticks" bug (#143 follow-up):
    a long entry's label/color must not bleed onto subsequent short presses.
    """

    def test_unset_before_any_press(self):
        state = _make_state(1, 1)
        assert state.last_fired is None

    def test_short_press_sets_short(self):
        state = _make_state(1, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes", "short": [{"up": [CC(20, 127)]}]}
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert state.last_fired == "short"

    def test_long_press_sets_long(self):
        state = _make_state(1, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes", "long": [{"down": [CC(21, 127)]}]}
        dispatch_keytimes_events(["short_down", "long_down", "long_up"], state, cfg, cb)
        assert state.last_fired == "long"

    def test_short_after_long_flips_back_to_short(self):
        # The user's PUP config: short msg in `up`, long msg in `down`. A long
        # press then a short tap must leave last_fired == "short" so the render
        # shows the short label, not the stuck long label.
        state = _make_state(1, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"up": [CC(20, 1)], "label": "PUP"}],
               "long": [{"down": [CC(20, 4)], "label": "BUP"}]}
        dispatch_keytimes_events(["short_down", "long_down", "long_up"], state, cfg, cb)
        assert state.last_fired == "long"
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        assert state.last_fired == "short"

    def test_empty_slot_does_not_change_last_fired(self):
        # short_down on an entry whose down slot is empty fires nothing, so it
        # must not claim last_fired (mirrors the slot-has-content rule).
        state = _make_state(1, 1)
        cb, _ = _msg_collector()
        cfg = {"mode": "keytimes", "short": [{"up": [CC(20, 127)]}]}
        dispatch_keytimes_events(["short_down"], state, cfg, cb)
        assert state.last_fired is None


class TestDispatchReverbShimmerScenario:
    """End-to-end trace of the reverb+shimmer scenario.

    Config (button-level mode: "keytimes"):
      short: 2 entries — reverb on (color: white), reverb off (color: off)
      long:  2 entries — shimmer on (color: blue), shimmer off (color: white)
    """

    def setup_method(self):
        self.state = _make_state(2, 2)
        self.cfg = {
            "mode": "keytimes",
            "short": [
                {"up": [CC(20, 127)], "color": "white"},  # reverb on
                {"up": [CC(20, 0)],   "color": "off"},    # reverb off
            ],
            "long": [
                {"down": [CC(21, 127)], "color": "blue"},   # shimmer on
                {"down": [CC(21, 0)],   "color": "white"},  # shimmer off
            ],
        }

    def test_full_sequence(self):
        cb, captured = _msg_collector()
        # 1. Short tap -> reverb on
        dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        assert captured == [CC(20, 127)]  # only "up" defined; "short_down" had no messages
        assert self.state.short_cycle.index == 1
        assert self.state.short_color == "white"
        assert self.state.long_color is None
        captured.clear()

        # 2. Long hold -> shimmer on
        dispatch_keytimes_events(["short_down", "long_down", "long_up"], self.state, self.cfg, cb)
        assert captured == [CC(21, 127)]  # long entry[0].down
        # short_cycle: short_down fired BUT short entry[1] has no down messages,
        # so the cycle does NOT advance — the slot-has-content rule applies to
        # cycle advancement too. short_cycle.index stays at 1.
        assert self.state.short_cycle.index == 1
        # long_cycle: long_down fired with messages -> advance to 1
        assert self.state.long_cycle.index == 1
        # short_color: short_down on short entry[1] has no down messages, so render
        # state is NOT updated. short_color stays at "white" from step 1.
        # The strict slot-has-content rule: an empty slot is silent on every axis
        # (MIDI, LED, cycle) — long-press toggling shimmer doesn't leak into the
        # short layer.
        assert self.state.short_color == "white"
        assert self.state.long_color == "blue"
        captured.clear()

        # 3. Long hold -> shimmer off
        dispatch_keytimes_events(["short_down", "long_down", "long_up"], self.state, self.cfg, cb)
        # short_down on entry[0] (after previous wrap-to-0): color "white"
        # short_cycle advances to 1
        # long_down on entry[1]: color "white", message CC(21, 0)
        # long_cycle advances to 0
        assert captured == [CC(21, 0)]
        assert self.state.short_cycle.index == 1
        assert self.state.long_cycle.index == 0
        assert self.state.short_color == "white"
        assert self.state.long_color == "white"
        captured.clear()

        # 4. Short tap -> reverb off
        dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        # short entry[1]: up message CC(20, 0), color "off"
        assert captured == [CC(20, 0)]
        # short_cycle advances to 0 (wrap)
        assert self.state.short_cycle.index == 0
        assert self.state.short_color == "off"


class TestDispatchMixedSlotPopulation:
    """Test 1: a single cycle whose entries have different slot population —
    one with both down+up, one with down only, one with up only. Each entry
    should fire/render/advance only on the events whose slots have content.
    The cycle index must advance once per physical press as long as at least
    one of that cycle's events fired with content."""

    def setup_method(self):
        self.state = _make_state(3, 0)
        self.cfg = {
            "mode": "keytimes",
            "short": [
                # entry 0: both slots populated
                {"down": [CC(20, 1)], "up": [CC(20, 2)], "color": "red"},
                # entry 1: down only
                {"down": [CC(20, 3)],                    "color": "green"},
                # entry 2: up only
                {                     "up": [CC(20, 4)], "color": "blue"},
            ],
        }

    def test_tap_at_entry_with_both_slots(self):
        cb, captured = _msg_collector()
        dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        # Both slots fire MIDI, render uses entry 0's color, cycle advances to 1.
        assert captured == [CC(20, 1), CC(20, 2)]
        assert self.state.short_color == "red"
        assert self.state.short_cycle.index == 1

    def test_tap_at_entry_with_down_only(self):
        cb, captured = _msg_collector()
        # advance to entry 1 first
        dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        assert self.state.short_cycle.index == 1
        captured.clear()

        dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        # Only the down slot fires; up is empty. Render updates from the down event.
        # Cycle still advances because short_down fired with content.
        assert captured == [CC(20, 3)]
        assert self.state.short_color == "green"
        assert self.state.short_cycle.index == 2

    def test_tap_at_entry_with_up_only(self):
        cb, captured = _msg_collector()
        # advance to entry 2
        dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        assert self.state.short_cycle.index == 2
        captured.clear()

        dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        # short_down has no content → no MIDI, no render, no cycle flag from this event.
        # short_up has content → fires MIDI, renders, sets flag → cycle advances (wraps).
        assert captured == [CC(20, 4)]
        assert self.state.short_color == "blue"
        assert self.state.short_cycle.index == 0

    def test_full_cycle_returns_to_start(self):
        cb, captured = _msg_collector()
        for _ in range(3):
            dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        # After three taps the cycle index is back at 0. The LED still shows
        # whatever the last entry rendered (entry 2's "blue") — the color only
        # updates to "red" again on the next press, when entry 0 fires.
        assert self.state.short_cycle.index == 0
        assert self.state.short_color == "blue"
        # One more press confirms entry 0 fires next and re-renders red.
        dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        assert self.state.short_color == "red"
        assert self.state.short_cycle.index == 1

    def test_entry_with_no_slots_is_noop(self):
        # A color-only entry with no down or up content is a no-op: no MIDI,
        # no render, no cycle advance. The cycle gets stuck at this entry.
        state = _make_state(2, 0)
        cb, captured = _msg_collector()
        cfg = {"mode": "keytimes",
               "short": [{"color": "purple"},                    # no slots
                         {"up": [CC(20, 9)], "color": "yellow"}]}
        dispatch_keytimes_events(["short_down", "short_up"], state, cfg, cb)
        # Entry 0 has no slot content → silent on every axis.
        assert captured == []
        assert state.short_color is None
        assert state.short_cycle.index == 0  # stays put — color-only entries are no-ops


class TestDispatchIndependentCycleProgression:
    """Test 2: short cycle of 3, long cycle of 2, with empty *_down slots on
    both cycles. Confirms that long presses advance only the long cycle and
    short taps advance only the short cycle, even though short_down fires on
    every physical press.
    """

    def setup_method(self):
        self.state = _make_state(3, 2)
        self.cfg = {
            "mode": "keytimes",
            "short": [
                {"up": [CC(20, 1)], "color": "red"},
                {"up": [CC(20, 2)], "color": "green"},
                {"up": [CC(20, 3)], "color": "blue"},
            ],
            "long": [
                {"down": [CC(21, 1)], "color": "white"},
                {"down": [CC(21, 2)], "color": "off"},
            ],
        }

    def test_taps_and_longs_advance_independently(self):
        cb, captured = _msg_collector()
        # Pattern: tap, tap, tap, long, tap, long, tap.
        # Short cycle (len 3) should reach: 1, 2, 0, 0, 1, 1, 2.
        # Long  cycle (len 2) should reach: 0, 0, 0, 1, 1, 0, 0.
        steps = [
            ("tap",  ["short_down", "short_up"]),
            ("tap",  ["short_down", "short_up"]),
            ("tap",  ["short_down", "short_up"]),
            ("long", ["short_down", "long_down", "long_up"]),
            ("tap",  ["short_down", "short_up"]),
            ("long", ["short_down", "long_down", "long_up"]),
            ("tap",  ["short_down", "short_up"]),
        ]
        expected_short_idx = [1, 2, 0, 0, 1, 1, 2]
        expected_long_idx  = [0, 0, 0, 1, 1, 0, 0]

        for i, (kind, events) in enumerate(steps):
            dispatch_keytimes_events(events, self.state, self.cfg, cb)
            assert self.state.short_cycle.index == expected_short_idx[i], (
                f"after step {i} ({kind}): expected short_idx="
                f"{expected_short_idx[i]}, got {self.state.short_cycle.index}"
            )
            assert self.state.long_cycle.index == expected_long_idx[i], (
                f"after step {i} ({kind}): expected long_idx="
                f"{expected_long_idx[i]}, got {self.state.long_cycle.index}"
            )

    def test_long_presses_do_not_touch_short_state(self):
        cb, captured = _msg_collector()
        # Do a tap to advance short_color to "red".
        dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        assert self.state.short_color == "red"
        assert self.state.short_cycle.index == 1

        # Long press: short layer's color and cycle should remain untouched.
        captured.clear()
        dispatch_keytimes_events(["short_down", "long_down", "long_up"], self.state, self.cfg, cb)
        assert captured == [CC(21, 1)]
        assert self.state.short_color == "red"          # unchanged
        assert self.state.short_cycle.index == 1        # unchanged
        assert self.state.long_color == "white"
        assert self.state.long_cycle.index == 1

    def test_short_taps_do_not_touch_long_state(self):
        cb, captured = _msg_collector()
        # First trigger a long press to set long state to non-default.
        dispatch_keytimes_events(["short_down", "long_down", "long_up"], self.state, self.cfg, cb)
        assert self.state.long_color == "white"
        assert self.state.long_cycle.index == 1

        # Now several short taps; long state must not change.
        for _ in range(5):
            dispatch_keytimes_events(["short_down", "short_up"], self.state, self.cfg, cb)
        assert self.state.long_color == "white"         # unchanged
        assert self.state.long_cycle.index == 1         # unchanged
