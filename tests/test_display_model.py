"""Tests for core/display_model.py — pure screen model shared by firmware TFT,
the browser demo, and these tests."""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.button import KeytimesButtonState
from core.display_model import (compute_layout, button_visual, keytimes_visual,
                                build_screen)


class TestComputeLayout:
    def test_std10_geometry(self):
        lo = compute_layout(button_count=10, button_font_height=20)
        assert lo["button_width"] == 46
        assert lo["button_height"] == 30          # font 20 + 10 padding
        assert lo["row_size"] == 5
        # First button, top row
        assert lo["positions"][0] == (1, 5)
        # Second button steps by spacing 48
        assert lo["positions"][1] == (49, 5)
        # Sixth button starts the bottom row: y = 240 - 30 - 5
        assert lo["positions"][5] == (1, 205)

    def test_mini6_geometry(self):
        lo = compute_layout(button_count=6, button_font_height=20)
        assert lo["button_width"] == 70
        assert lo["row_size"] == 3
        assert lo["positions"][3] == (1, 205)     # bottom row starts at index 3

    def test_nano4_geometry(self):
        lo = compute_layout(button_count=4, button_font_height=20)
        assert lo["button_width"] == 100
        assert lo["row_size"] == 2
        assert lo["positions"][1] == (121, 5)     # spacing 120

    def test_label_centers(self):
        lo = compute_layout(button_count=10, button_font_height=20)
        # Centered in the box: x + w//2, y + h//2
        assert lo["centers"][0] == (1 + 46 // 2, 5 + 30 // 2)


class TestButtonVisual:
    def test_on_uses_full_color(self):
        v = button_visual({"color": "green"}, on=True)
        assert v == {"label_color": 0x00FF00, "box_color": 0x00FF00}

    def test_off_uses_dim_color(self):
        # dim_color factor 0.15: 255 -> 38 = 0x26
        v = button_visual({"color": "green"}, on=False)
        assert v == {"label_color": 0x002600, "box_color": 0x002600}

    def test_off_mode_off_still_dims_display(self):
        # get_off_color_for_display ignores off_mode — labels stay visible
        v = button_visual({"color": "green", "off_mode": "off"}, on=False)
        assert v["label_color"] == 0x002600

    def test_missing_color_falls_back_white(self):
        v = button_visual({}, on=True)
        assert v["label_color"] == 0xFFFFFF


def _kt_state(**kw):
    st = KeytimesButtonState(threshold_ms=500, short_length=2, long_length=2)
    for k, v in kw.items():
        setattr(st, k, v)
    return st


class TestKeytimesVisual:
    CFG = {"label": "VERB", "color": "white", "mode": "keytimes"}

    def test_before_first_press_shows_button_label_and_color(self):
        v = keytimes_visual(_kt_state(), self.CFG)
        assert v["text"] == "VERB"
        assert v["box_color"] == 0xFFFFFF      # falls back to button color
        assert v["label_color"] == 0xFFFFFF

    def test_short_fired_shows_short_label_and_color(self):
        st = _kt_state(last_fired="short", short_color="green", short_label="ON")
        v = keytimes_visual(st, self.CFG)
        assert v["text"] == "ON"
        assert v["box_color"] == 0x00FF00

    def test_long_label_falls_back_to_short_then_button(self):
        # 143: a labelless long entry shows the prior short label
        st = _kt_state(last_fired="long", short_label="ON")
        v = keytimes_visual(st, self.CFG)
        assert v["text"] == "ON"
        st2 = _kt_state(last_fired="long")
        assert keytimes_visual(st2, self.CFG)["text"] == "VERB"

    def test_last_fired_short_suppresses_stale_long_color(self):
        # 157: long color must not stick once a short press fires
        st = _kt_state(last_fired="short", short_color="green",
                       long_color="magenta")
        v = keytimes_visual(st, self.CFG)
        assert v["box_color"] == 0x00FF00

    def test_long_overlay_keeps_long_color_over_short(self):
        cfg = dict(self.CFG, long_overlay=True)
        st = _kt_state(last_fired="short", short_color="green",
                       long_color="magenta")
        assert keytimes_visual(st, cfg)["box_color"] == 0xFF00FF

    def test_kill_switch_black_label_falls_back_to_button_color(self):
        # 143: black-on-black guard — label color falls back to button color
        st = _kt_state(last_fired="short", short_color="off")
        v = keytimes_visual(st, self.CFG)
        assert v["box_color"] == 0x000000       # LED/box genuinely off
        assert v["label_color"] == 0xFFFFFF     # label stays legible

    def test_dim_stripped_from_label_color(self):
        # 143: label color renders at full brightness even for dim entries
        st = _kt_state(last_fired="short", short_color="green", short_dim=True)
        v = keytimes_visual(st, self.CFG)
        assert v["box_color"] == 0x002600       # box honors dim
        assert v["label_color"] == 0x00FF00     # label does not

    def test_label_truncated_to_six_chars(self):
        st = _kt_state(last_fired="short", short_label="LONGLABEL")
        assert keytimes_visual(st, self.CFG)["text"] == "LONGLA"


class TestBuildScreen:
    BUTTONS = [{"label": "TSC", "color": "green"},
               {"label": "CHOR", "color": "blue"}]

    def test_screen_shape(self):
        s = build_screen(self.BUTTONS, button_count=10, button_font_height=20,
                         has_expression=False, exp1_label="EXP1", exp2_label="EXP2")
        assert s["size"] == (240, 240)
        assert len(s["buttons"]) == 10
        assert s["status"] == {"x": 120, "y": 120, "text": "Ready",
                               "color": 0xFFFFFF}
        assert s["expression"] == []

    def test_button_entries(self):
        s = build_screen(self.BUTTONS, 10, 20, False, "EXP1", "EXP2")
        b0 = s["buttons"][0]
        assert (b0["x"], b0["y"]) == (1, 5)
        assert (b0["w"], b0["h"]) == (46, 30)
        assert b0["text"] == "TSC"
        assert b0["label_color"] == 0x002600     # boots in off state (dim green)
        # Missing config beyond the provided list falls back to numbered white
        assert s["buttons"][2]["text"] == "3"

    def test_expression_entries(self):
        s = build_screen(self.BUTTONS, 10, 20, True, "VOL", "WAH")
        assert s["expression"][0] == {"x": 70, "y": 150, "text": "VOL: ---",
                                      "color": 0x888888}
        assert s["expression"][1]["text"] == "WAH: ---"

    def test_label_truncation(self):
        s = build_screen([{"label": "LONGLABEL", "color": "red"}], 4, 20,
                         False, "EXP1", "EXP2")
        assert s["buttons"][0]["text"] == "LONGLA"
