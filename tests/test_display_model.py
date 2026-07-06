"""Tests for core/display_model.py — pure screen model shared by firmware TFT,
the browser demo, and these tests."""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.display_model import compute_layout


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
