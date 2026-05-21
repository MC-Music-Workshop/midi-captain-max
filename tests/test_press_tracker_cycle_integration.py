"""Integration: PressTracker + PressCycle traces real-world scenarios.

Verifies that the timing classifier and the per-class cycle counters compose
the way the keytimes-mode design intends. See docs/plans/2026-05-13-issue-48-press-timings.md.
"""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.button import PressTracker, PressCycle


def _advance_cycles(events, short_cycle, long_cycle):
    """Advance the relevant cycle at most once per call (one physical press → one advance per class with events)."""
    fired_short = any(e in ("short_down", "short_up") for e in events)
    fired_long = any(e in ("long_down", "long_up") for e in events)
    if fired_short:
        short_cycle.advance()
    if fired_long:
        long_cycle.advance()


def test_reverb_shimmer_sequence():
    """User's OEM config: short-press cycles reverb on/off; long-press cycles shimmer on/off.

    Sequence:
      1. short tap  -> reverb on
      2. long hold  -> shimmer on
      3. long hold  -> shimmer off
      4. short tap  -> reverb off
    """
    tracker = PressTracker(threshold_ms=500)
    short = PressCycle(length=2)
    long_ = PressCycle(length=2)

    assert short.index == 0
    assert long_.index == 0

    # 1. Short tap -> reverb on
    tracker.update(pressed=True, now=0.0)
    events = tracker.update(pressed=False, now=0.1)
    assert "short_up" in events
    _advance_cycles(events, short, long_)
    assert short.index == 1
    assert long_.index == 0

    # 2. Long hold -> shimmer on
    tracker.update(pressed=True, now=1.0)
    events_threshold = tracker.update(pressed=True, now=1.5)
    events_release = tracker.update(pressed=False, now=1.7)
    assert "long_down" in events_threshold
    assert "long_up" in events_release
    _advance_cycles(events_threshold + events_release, short, long_)
    assert short.index == 1  # short cycle unchanged — no short event fired
    assert long_.index == 1

    # 3. Long hold -> shimmer off (wraps to 0)
    tracker.update(pressed=True, now=2.0)
    events_threshold = tracker.update(pressed=True, now=2.5)
    events_release = tracker.update(pressed=False, now=2.7)
    _advance_cycles(events_threshold + events_release, short, long_)
    assert short.index == 1
    assert long_.index == 0

    # 4. Short tap -> reverb off (wraps to 0)
    tracker.update(pressed=True, now=3.0)
    events = tracker.update(pressed=False, now=3.1)
    _advance_cycles(events, short, long_)
    assert short.index == 0
    assert long_.index == 0


def test_short_tap_with_both_down_and_up_advances_once():
    """A short tap with both short_down and short_up firing advances short cycle by 1, not 2.

    Rule: each cycle advances at most once per physical press, when ≥1 of its events fired.
    """
    tracker = PressTracker(threshold_ms=500)
    short = PressCycle(length=2)
    long_ = PressCycle(length=2)

    events_down = tracker.update(pressed=True, now=0.0)
    events_up = tracker.update(pressed=False, now=0.1)
    assert events_down == ["short_down"]
    assert events_up == ["short_up"]

    # Caller collects events from one physical press and advances cycles once total.
    all_events = events_down + events_up
    _advance_cycles(all_events, short, long_)
    assert short.index == 1  # advanced once, not twice
    assert long_.index == 0


def test_long_press_with_short_down_defined_advances_both_cycles():
    """A long press where both short_down and long_down would fire advances both cycles by 1.

    Per advancement rule: each cycle advances if ≥1 of its events fired. short_down belongs to
    short cycle; long_down belongs to long cycle. Different cycles, each fires once → each advances once.
    """
    tracker = PressTracker(threshold_ms=500)
    short = PressCycle(length=3)
    long_ = PressCycle(length=3)

    events_down = tracker.update(pressed=True, now=0.0)
    events_threshold = tracker.update(pressed=True, now=0.5)
    events_release = tracker.update(pressed=False, now=0.7)
    assert events_down == ["short_down"]
    assert events_threshold == ["long_down"]
    assert events_release == ["long_up"]

    all_events = events_down + events_threshold + events_release
    _advance_cycles(all_events, short, long_)
    assert short.index == 1  # short_down fired -> short advanced
    assert long_.index == 1  # long_down/long_up fired -> long advanced


def test_asymmetric_cycle_lengths_lead_button():
    """Lead button: 3 short states (Clean/Crunch/Lead) and 2 long states (Hall/Plate).

    Verifies cycle lengths are independent — short and long wrap at different periods.
    """
    tracker = PressTracker(threshold_ms=500)
    short = PressCycle(length=3)
    long_ = PressCycle(length=2)

    # 3 short taps: 0 -> 1 -> 2 -> 0 (wrap)
    for i, t in enumerate([0.0, 1.0, 2.0]):
        tracker.update(pressed=True, now=t)
        events = tracker.update(pressed=False, now=t + 0.1)
        _advance_cycles(events, short, long_)
    assert short.index == 0  # 3 advances mod 3 = 0
    assert long_.index == 0  # no long events fired

    # 5 long holds: 0 -> 1 -> 0 -> 1 -> 0 -> 1 (wrap several times)
    for i in range(5):
        t = 10.0 + i * 1.0
        tracker.update(pressed=True, now=t)
        ev1 = tracker.update(pressed=True, now=t + 0.5)
        ev2 = tracker.update(pressed=False, now=t + 0.7)
        _advance_cycles(ev1 + ev2, short, long_)
    assert short.index == 0  # short cycle untouched
    assert long_.index == 1  # 5 advances mod 2 = 1
