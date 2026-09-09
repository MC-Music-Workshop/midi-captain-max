"""Tests for core/cc_step.py — pure inc/dec CC value math (issue #11)."""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.cc_step import (
  is_cc_step_button,
  cc_step_key,
  cc_step_initial,
  cc_step_clamp,
  cc_step_next,
  cc_slot_index,
  cc_slot_color,
  cc_slot_name,
  cc_slot_text,
  step_value,
  slot_index,
  slot_value,
  step_slot,
)


class TestStepValue:
  def test_plain_step(self):
    assert step_value(10, 1, 0, 127, True) == 11
    assert step_value(10, -3, 0, 127, True) == 7

  def test_wrap_past_max_lands_on_min(self):
    assert step_value(127, 1, 0, 127, True) == 0
    # A big step that overshoots still lands ON min, not modulo.
    assert step_value(125, 5, 0, 127, True) == 0

  def test_wrap_below_min_lands_on_max(self):
    assert step_value(0, -1, 0, 127, True) == 127
    assert step_value(2, -5, 0, 127, True) == 127

  def test_wrap_honors_custom_bounds(self):
    assert step_value(100, 1, 10, 100, True) == 10
    assert step_value(10, -1, 10, 100, True) == 100

  def test_clamp_when_wrap_disabled(self):
    assert step_value(126, 5, 0, 127, False) == 127
    assert step_value(127, 1, 0, 127, False) == 127
    assert step_value(1, -5, 0, 127, False) == 0

  def test_landing_exactly_on_bound_does_not_wrap(self):
    assert step_value(126, 1, 0, 127, True) == 127
    assert step_value(1, -1, 0, 127, True) == 0


class TestSlotMath:
  def test_four_slots_full_range_midpoints(self):
    # 128 values / 4 slots = 32 wide; middles at 16, 48, 80, 112.
    assert [slot_value(i, 0, 127, 4) for i in range(4)] == [16, 48, 80, 112]

  def test_midpoints_map_back_to_their_slot(self):
    for slots in range(2, 17):
      for i in range(slots):
        assert slot_index(slot_value(i, 0, 127, slots), 0, 127, slots) == i

  def test_slot_index_edges(self):
    assert slot_index(0, 0, 127, 4) == 0
    assert slot_index(31, 0, 127, 4) == 0
    assert slot_index(32, 0, 127, 4) == 1
    assert slot_index(127, 0, 127, 4) == 3

  def test_slot_index_clamps_out_of_range_values(self):
    assert slot_index(-5, 0, 127, 4) == 0
    assert slot_index(200, 0, 127, 4) == 3
    assert slot_index(5, 10, 100, 3) == 0

  def test_custom_range_midpoints_stay_inside_range(self):
    for i in range(3):
      v = slot_value(i, 10, 100, 3)
      assert 10 <= v <= 100

  def test_step_slot_advances_to_next_midpoint(self):
    assert step_slot(16, 1, 0, 127, 4, True) == 48
    assert step_slot(0, 1, 0, 127, 4, True) == 48   # any value in slot 0 -> slot 1
    assert step_slot(48, -1, 0, 127, 4, True) == 16

  def test_step_slot_wraps(self):
    assert step_slot(112, 1, 0, 127, 4, True) == 16
    assert step_slot(16, -1, 0, 127, 4, True) == 112

  def test_step_slot_clamps_without_wrap(self):
    assert step_slot(112, 1, 0, 127, 4, False) == 112
    assert step_slot(16, -1, 0, 127, 4, False) == 16


def step_btn(**over):
  btn = {"type": "cc_inc", "cc": 30, "channel": 2, "cc_step": 1, "cc_min": 0,
         "cc_max": 127, "cc_wrap": True, "label": "VOL", "color": "white"}
  btn.update(over)
  return btn


def slot_btn(**over):
  btn = {"type": "cc_inc", "cc": 31, "channel": 0, "cc_slots": 4, "cc_min": 0,
         "cc_max": 127, "cc_wrap": True, "label": "AMP", "color": "white"}
  btn.update(over)
  return btn


class TestButtonHelpers:
  def test_is_cc_step_button(self):
    assert is_cc_step_button(step_btn())
    assert is_cc_step_button(step_btn(type="cc_dec"))
    assert is_cc_step_button(slot_btn())
    # keytimes button carrying cc-step fields (validator copies them on)
    assert is_cc_step_button({"mode": "keytimes", "type": "cc", "cc": 5, "cc_step": 1})
    assert not is_cc_step_button({"type": "cc", "cc": 20})
    assert not is_cc_step_button({"mode": "keytimes", "type": "cc"})

  def test_key_is_channel_then_cc(self):
    assert cc_step_key(step_btn()) == (2, 30)
    assert cc_step_key({"type": "cc_inc"}) == (0, 0)

  def test_initial_defaults_to_min(self):
    assert cc_step_initial(step_btn()) == 0
    assert cc_step_initial(step_btn(cc_min=10)) == 10
    assert cc_step_initial(step_btn(cc_initial=64)) == 64

  def test_clamp_rx_into_range(self):
    assert cc_step_clamp(step_btn(cc_min=10, cc_max=100), 127) == 100
    assert cc_step_clamp(step_btn(cc_min=10, cc_max=100), 0) == 10
    assert cc_step_clamp(step_btn(), 64) == 64

  def test_next_step_mode(self):
    assert cc_step_next(step_btn(cc_step=5), 0, 1) == 5
    assert cc_step_next(step_btn(cc_step=5), 0, -1) == 127
    assert cc_step_next(step_btn(cc_step=5, cc_wrap=False), 0, -1) == 0

  def test_next_slot_mode_ignores_cc_step(self):
    assert cc_step_next(slot_btn(cc_step=50), 16, 1) == 48
    assert cc_step_next(slot_btn(), 16, -1) == 112

  def test_slot_color_falls_back_to_button_color(self):
    btn = slot_btn(cc_slot_colors=["red", "green"], color="blue")
    assert cc_slot_color(btn, 16) == "red"
    assert cc_slot_color(btn, 48) == "green"
    assert cc_slot_color(btn, 80) == "blue"   # no entry -> button color
    assert cc_slot_color(slot_btn(), 16) == "white"

  def test_slot_name_and_text(self):
    btn = slot_btn(cc_slot_names=["MARSH", "FENDER"])
    assert cc_slot_name(btn, 16) == "MARSH"
    assert cc_slot_text(btn, 48) == "FENDER"
    assert cc_slot_name(btn, 80) is None
    assert cc_slot_text(btn, 80) == "AMP 3/4"
    assert cc_slot_text(slot_btn(), 112) == "AMP 4/4"

  def test_empty_name_entry_falls_back_to_position(self):
    btn = slot_btn(cc_slot_names=["", "TWO"])
    assert cc_slot_text(btn, 0) == "AMP 1/4"
    assert cc_slot_text(btn, 48) == "TWO"

  def test_slot_index_helper(self):
    assert cc_slot_index(slot_btn(), 0) == 0
    assert cc_slot_index(slot_btn(), 127) == 3
