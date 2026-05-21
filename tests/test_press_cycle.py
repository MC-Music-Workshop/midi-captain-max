"""Tests for press-cycle state (PressCycle).

PressCycle tracks the current entry index for one timing class (short or long).
A keytimes-mode button has two PressCycles, one per class, advancing independently.
See docs/plans/2026-05-13-issue-48-press-timings.md for design.
"""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

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

    def test_advance_continues_wrapping(self):
        cycle = PressCycle(length=2)
        for _ in range(5):
            cycle.advance()
        # 5 advances mod 2 = 1
        assert cycle.index == 1

    def test_length_one_advance_stays_at_zero(self):
        cycle = PressCycle(length=1)
        cycle.advance()
        assert cycle.index == 0

    def test_length_zero_no_advance(self):
        """Zero-length cycle (no events defined) doesn't change index."""
        cycle = PressCycle(length=0)
        cycle.advance()
        assert cycle.index == 0


class TestPressCycleReset:
    def test_reset_from_zero(self):
        cycle = PressCycle(length=3)
        cycle.reset()
        assert cycle.index == 0

    def test_reset_from_middle(self):
        cycle = PressCycle(length=3)
        cycle.advance()
        cycle.advance()
        cycle.reset()
        assert cycle.index == 0
