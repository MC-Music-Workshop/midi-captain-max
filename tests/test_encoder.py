"""Tests for core/encoder.py — pure encoder value/slot logic shared by firmware
and the browser demo."""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.encoder import EncoderState


class TestNormalMode:
    def test_initial_clamped(self):
        assert EncoderState(11, initial=200).value == 127
        assert EncoderState(11, initial=-5).value == 0

    def test_turn_emits_value(self):
        enc = EncoderState(11, initial=64)
        assert enc.turn(1) == {"type": "cc", "cc": 11, "value": 65}
        assert enc.turn(-2) == {"type": "cc", "cc": 11, "value": 63}

    def test_clamps_at_top(self):
        enc = EncoderState(11, initial=127)
        # Still emits at the boundary (firmware sends on every detent), value pinned.
        assert enc.turn(1) == {"type": "cc", "cc": 11, "value": 127}

    def test_clamps_at_bottom(self):
        enc = EncoderState(11, initial=0)
        assert enc.turn(-1) == {"type": "cc", "cc": 11, "value": 0}


class TestSteppedMode:
    def test_initial_slot(self):
        # 5 slots, slot_size 25; value 64 -> slot 2
        enc = EncoderState(11, initial=64, steps=5)
        assert enc.slot == 2

    def test_emits_slot_only_on_change(self):
        enc = EncoderState(11, initial=64, steps=5)  # slot 2
        assert enc.turn(1) is None            # 65, still slot 2
        assert enc.turn(-40) == {"type": "cc", "cc": 11, "value": 1}  # 25 -> slot 1
        # wait: 65-40=25 -> 25//25 = 1

    def test_slot_clamped_to_max(self):
        enc = EncoderState(11, initial=120, steps=5)  # 120//25 = 4
        assert enc.slot == 4
        assert enc.turn(10) is None            # pinned at 127 -> slot 4, unchanged

    def test_steps_one_is_normal_mode(self):
        enc = EncoderState(11, initial=64, steps=1)
        assert enc.steps is None
        assert enc.turn(1) == {"type": "cc", "cc": 11, "value": 65}
