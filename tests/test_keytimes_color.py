"""Tests for compute_keytimes_led_color render rule (#48).

The two-layer render rule:
- short.color == "off"        -> LED off (kill switch)
- long.color set (not "off")  -> LED = long.color (long modifies short)
- short.color set             -> LED = short.color
- else                        -> LED off
"""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.colors import compute_keytimes_led_color, get_color, dim_color, COLORS

OFF = COLORS["off"]


class TestKeytimesRenderRule:
    def test_both_unset_returns_off(self):
        assert compute_keytimes_led_color(None, False, None, False) == OFF

    def test_short_only(self):
        assert compute_keytimes_led_color("blue", False, None, False) == get_color("blue")

    def test_long_only(self):
        # Long without short still renders (long is a modifier, not strictly require short).
        assert compute_keytimes_led_color(None, False, "blue", False) == get_color("blue")

    def test_both_set_long_wins(self):
        # User's reverb+shimmer expectation: blue (long) shows over white (short).
        result = compute_keytimes_led_color("white", False, "blue", False)
        assert result == get_color("blue")

    def test_short_off_kills_led_even_when_long_set(self):
        # The asymmetric kill-switch: short="off" overrides everything.
        result = compute_keytimes_led_color("off", False, "blue", False)
        assert result == OFF

    def test_long_off_falls_through_to_short(self):
        # Long="off" is just "no decoration" — short shows.
        result = compute_keytimes_led_color("white", False, "off", False)
        assert result == get_color("white")

    def test_both_off_returns_off(self):
        result = compute_keytimes_led_color("off", False, "off", False)
        assert result == OFF


class TestKeytimesRenderDim:
    def test_short_dim_applied_when_short_wins(self):
        result = compute_keytimes_led_color("blue", True, None, False)
        assert result == dim_color(get_color("blue"))

    def test_long_dim_applied_when_long_wins(self):
        result = compute_keytimes_led_color("white", False, "blue", True)
        assert result == dim_color(get_color("blue"))

    def test_short_dim_ignored_when_long_wins(self):
        # When long wins, short's dim doesn't apply.
        result = compute_keytimes_led_color("blue", True, "red", False)
        assert result == get_color("red")

    def test_long_dim_ignored_when_short_wins(self):
        # When long is unset/off, long's dim is moot.
        result = compute_keytimes_led_color("blue", False, None, True)
        assert result == get_color("blue")

    def test_dim_does_not_apply_to_kill_switch(self):
        # short="off" with dim is still pure off (dim of off is off).
        result = compute_keytimes_led_color("off", True, "blue", False)
        assert result == OFF


class TestReverbShimmerTrace:
    """Trace the user's worked example sequence and verify each step renders correctly."""

    def test_initial(self):
        # Before any press: both layers unset.
        assert compute_keytimes_led_color(None, False, None, False) == OFF

    def test_step1_reverb_on_white(self):
        # short_up_1 fires: short = white. Long still unset.
        assert compute_keytimes_led_color("white", False, None, False) == get_color("white")

    def test_step2_shimmer_on_blue(self):
        # long_down_1 fires: long = blue. Short still white.
        # Result: blue (long modifies short)
        assert compute_keytimes_led_color("white", False, "blue", False) == get_color("blue")

    def test_step3_reverb_off_kills(self):
        # short_up_2 fires: short = off. Long still blue from earlier.
        # Result: off (kill switch)
        assert compute_keytimes_led_color("off", False, "blue", False) == OFF

    def test_step4_reverb_on_again_long_still_modifies(self):
        # short_up_1 fires again (wrapped): short = white. Long still blue.
        # Result: blue (long modifies short again)
        assert compute_keytimes_led_color("white", False, "blue", False) == get_color("blue")

    def test_step5_shimmer_off(self):
        # long_down_2 fires: long = white (config says "shimmer off, white"). Short still white.
        # Result: white (long set to white, wins)
        assert compute_keytimes_led_color("white", False, "white", False) == get_color("white")
