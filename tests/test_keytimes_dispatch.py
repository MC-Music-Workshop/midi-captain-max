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


CC = lambda cc, value: {"type": "cc", "cc": cc, "value": value}


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
