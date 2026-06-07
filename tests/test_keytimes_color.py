"""Tests for compute_keytimes_led_color render rule (#48).

The two-layer render rule:
- short.color == "off"        -> LED off (kill switch)
- long.color set (not "off")  -> LED = long.color (long modifies short)
- short.color set             -> LED = short.color
- button_color set            -> LED = button_color (fallback when all entries inherit)
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

    def test_both_unset_falls_back_to_button_color(self):
        # When every cycle entry leaves color as "(inherit)" (i.e. unset), neither
        # layer is ever populated. Fall back to the button-level color so the LED
        # still lights — matching the label precedence used in _render_keytimes_led.
        assert compute_keytimes_led_color(None, False, None, False, "red") == get_color("red")

    def test_short_set_overrides_button_color_fallback(self):
        assert compute_keytimes_led_color("blue", False, None, False, "red") == get_color("blue")

    def test_short_off_kills_led_even_with_button_color_fallback(self):
        # Kill-switch semantics must survive the new fallback path.
        assert compute_keytimes_led_color("off", False, None, False, "red") == OFF

    def test_button_color_fallback_applies_short_dim(self):
        # User scenario: every short entry is "(inherit)" but one has dim=true.
        # The button-level fallback should still dim.
        result = compute_keytimes_led_color(None, True, None, False, "red")
        assert result == dim_color(get_color("red"))

    def test_button_color_fallback_applies_long_dim(self):
        # Same dim path via the long layer.
        result = compute_keytimes_led_color(None, False, None, True, "red")
        assert result == dim_color(get_color("red"))

    def test_button_color_fallback_no_dim_when_neither_set(self):
        result = compute_keytimes_led_color(None, False, None, False, "red")
        assert result == get_color("red")

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


class TestIssue143LabelColorRegression:
    """Regression for #143: labels invisible when keytimes entry has dim=True.

    The bug: _render_keytimes_led set label text color = LED rgb.
    dim_color() produces 15% brightness — near-black, invisible on black display.

    The fix: label color recomputed with dim=False; black-on-black falls back to
    button color then white.

    These tests document the key properties the fix depends on.
    """

    # --- Confirm dimmed colors are near-black (would have been invisible) ---

    def test_dimmed_yellow_is_near_black(self):
        # PUP button: long_color="yellow", long_dim=True. The BUG produced this for label.
        dimmed = compute_keytimes_led_color(None, False, "yellow", True)
        assert dimmed == dim_color(get_color("yellow"))
        # Must be near-black: all channels < 50
        assert all(ch < 50 for ch in dimmed), f"expected near-black, got {dimmed}"

    def test_dimmed_blue_is_near_black(self):
        # PDN button: long_color="blue", long_dim=True.
        dimmed = compute_keytimes_led_color(None, False, "blue", True)
        assert dimmed == dim_color(get_color("blue"))
        assert all(ch < 50 for ch in dimmed), f"expected near-black, got {dimmed}"

    # --- Confirm fix: dim=False for label call produces visible colors ---

    def test_yellow_without_dim_is_visible(self):
        # The FIX passes dim=False when computing label_rgb.
        label_rgb = compute_keytimes_led_color(None, False, "yellow", False)
        assert label_rgb == get_color("yellow")
        assert any(ch >= 128 for ch in label_rgb), f"expected bright color, got {label_rgb}"

    def test_blue_without_dim_is_visible(self):
        label_rgb = compute_keytimes_led_color(None, False, "blue", False)
        assert label_rgb == get_color("blue")
        assert any(ch >= 128 for ch in label_rgb), f"expected bright color, got {label_rgb}"

    def test_short_dim_yellow_label_still_visible(self):
        # Same issue on short layer: short_color="yellow", short_dim=True.
        label_rgb = compute_keytimes_led_color("yellow", False, None, False)
        assert label_rgb == get_color("yellow")
        assert any(ch >= 128 for ch in label_rgb)

    # --- Confirm black-on-black fallback ---

    def test_no_color_on_any_layer_fallback_uses_button_color(self):
        # When both layers produce (0,0,0), fix falls back to button-level color.
        # compute_keytimes_led_color returns OFF when no colors set + no button color.
        result = compute_keytimes_led_color(None, False, None, False)
        assert not any(result), "both unset → OFF (black)"
        # Caller then applies: get_color(btn_config.get("color") or "white")
        fallback = get_color("white")
        assert any(fallback), "white fallback must be non-black"

    def test_led_and_label_colors_differ_when_dim_true(self):
        # Core regression assertion: LED rgb (dim=True) != label rgb (dim=False).
        led_rgb = compute_keytimes_led_color(None, False, "yellow", True)
        label_rgb = compute_keytimes_led_color(None, False, "yellow", False)
        assert led_rgb != label_rgb, "dim LED color must differ from full-brightness label color"
        assert led_rgb == dim_color(get_color("yellow"))
        assert label_rgb == get_color("yellow")
