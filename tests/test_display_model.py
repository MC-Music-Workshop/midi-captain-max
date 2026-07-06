"""Tests for core/display_model.py — pure screen model shared by firmware TFT,
the browser demo, and these tests."""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.display_model import compute_layout, button_visual


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
