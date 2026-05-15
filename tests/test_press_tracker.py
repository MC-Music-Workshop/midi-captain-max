"""Tests for press-timing classification (PressTracker).

PressTracker classifies a button's press lifecycle into four timing events
(short_down, short_up, long_down, long_up) based on a configurable threshold.
See docs/plans/2026-05-13-issue-48-press-timings.md for design.
"""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

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
        # Long press completes, then a fresh short press starts.
        tracker = PressTracker(threshold_ms=500)
        tracker.update(pressed=True, now=0.0)
        tracker.update(pressed=True, now=0.5)
        tracker.update(pressed=False, now=0.7)
        events = tracker.update(pressed=True, now=1.0)
        assert events == ["short_down"]

    def test_short_then_long(self):
        # Short press completes, then a long press fires long_down at threshold.
        tracker = PressTracker(threshold_ms=500)
        tracker.update(pressed=True, now=0.0)
        tracker.update(pressed=False, now=0.1)
        tracker.update(pressed=True, now=1.0)
        events = tracker.update(pressed=True, now=1.5)
        assert events == ["long_down"]


class TestPressTrackerEdgeCases:
    def test_threshold_exactly(self):
        """Crossing the threshold exactly counts as long (>= comparison)."""
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

    def test_custom_threshold(self):
        """Verify threshold is configurable."""
        tracker = PressTracker(threshold_ms=200)
        tracker.update(pressed=True, now=0.0)
        events_before = tracker.update(pressed=True, now=0.1)
        events_at = tracker.update(pressed=True, now=0.2)
        assert events_before == []
        assert events_at == ["long_down"]
