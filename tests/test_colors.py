"""
Tests for color utility functions.

Tests the actual core/colors.py module.
"""

import pytest
import sys
from pathlib import Path

# Add firmware/dev to path so we can import core modules
FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.colors import COLORS, get_color, dim_color, rgb_to_hex, get_off_color


class TestGetColor:
    """Tests for get_color function."""
    
    def test_known_colors(self):
        assert get_color("red") == (255, 0, 0)
        assert get_color("green") == (0, 255, 0)
        assert get_color("blue") == (0, 0, 255)
    
    def test_case_insensitive(self):
        assert get_color("RED") == (255, 0, 0)
        assert get_color("Red") == (255, 0, 0)
        assert get_color("rEd") == (255, 0, 0)
    
    def test_unknown_color_returns_white(self):
        assert get_color("fuschia") == (255, 255, 255)
        assert get_color("chartreuse") == (255, 255, 255)
        assert get_color("") == (255, 255, 255)


class TestDimColor:
    """Tests for dim_color function."""
    
    def test_dim_red(self):
        result = dim_color((255, 0, 0))
        assert result == (38, 0, 0)  # int(255 * 0.15) = 38
    
    def test_dim_white(self):
        result = dim_color((255, 255, 255))
        assert result == (38, 38, 38)
    
    def test_custom_factor(self):
        result = dim_color((200, 100, 50), factor=0.5)
        assert result == (100, 50, 25)
    
    def test_already_dim(self):
        result = dim_color((10, 10, 10))
        assert result == (1, 1, 1)


class TestRgbToHex:
    """Tests for rgb_to_hex function."""

    def test_red(self):
        assert rgb_to_hex((255, 0, 0)) == 0xFF0000

    def test_green(self):
        assert rgb_to_hex((0, 255, 0)) == 0x00FF00

    def test_blue(self):
        assert rgb_to_hex((0, 0, 255)) == 0x0000FF

    def test_white(self):
        assert rgb_to_hex((255, 255, 255)) == 0xFFFFFF

    def test_mixed(self):
        assert rgb_to_hex((128, 64, 32)) == 0x804020


class TestGetOffColor:
    """Tests for get_off_color function (for LEDs)."""

    def test_off_mode_returns_black(self):
        """Off mode should return black (completely off) for LEDs."""
        color = (255, 0, 0)  # Red
        result = get_off_color(color, off_mode="off")
        assert result == (0, 0, 0)

    def test_dim_mode_returns_dim_color(self):
        """Dim mode should return dim color."""
        color = (0, 255, 0)  # Green
        result = get_off_color(color, off_mode="dim")
        assert result == dim_color(color)

