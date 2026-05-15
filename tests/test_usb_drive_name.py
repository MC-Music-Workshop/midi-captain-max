"""
Tests for USB drive name validation.
"""

import sys
import os

# Add firmware/dev to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../firmware/dev"))

from core.config import (
    validate_usb_drive_name,
    get_usb_drive_name,
    get_dev_mode,
    get_midi_thru_usb,
    get_midi_thru_din,
)


def test_validate_usb_drive_name_valid():
    """Test valid drive names pass through correctly."""
    assert validate_usb_drive_name("MYDEVICE") == "MYDEVICE"
    assert validate_usb_drive_name("DEVICE123") == "DEVICE123"
    assert validate_usb_drive_name("ABC_DEF") == "ABC_DEF"
    assert validate_usb_drive_name("A") == "A"


def test_validate_usb_drive_name_lowercase():
    """Test lowercase names are converted to uppercase."""
    assert validate_usb_drive_name("mydevice") == "MYDEVICE"
    assert validate_usb_drive_name("Device123") == "DEVICE123"


def test_validate_usb_drive_name_max_length():
    """Test names longer than 11 chars are truncated."""
    assert validate_usb_drive_name("VERYLONGNAME123") == "VERYLONGNAM"
    assert validate_usb_drive_name("12345678901234567890") == "12345678901"


def test_validate_usb_drive_name_special_chars():
    """Test special characters are removed."""
    assert validate_usb_drive_name("MY-DEVICE") == "MYDEVICE"
    assert validate_usb_drive_name("MY DEVICE") == "MYDEVICE"
    assert validate_usb_drive_name("MY@DEVICE#") == "MYDEVICE"
    assert validate_usb_drive_name("HELLO!WORLD") == "HELLOWORLD"


def test_validate_usb_drive_name_underscore_allowed():
    """Test underscores are preserved."""
    assert validate_usb_drive_name("MY_DEVICE") == "MY_DEVICE"
    assert validate_usb_drive_name("A_B_C") == "A_B_C"


def test_validate_usb_drive_name_empty_fallback():
    """Test empty/invalid names fall back to MIDICAPTAIN."""
    assert validate_usb_drive_name("") == "MIDICAPTAIN"
    assert validate_usb_drive_name(None) == "MIDICAPTAIN"
    assert validate_usb_drive_name("   ") == "MIDICAPTAIN"
    assert validate_usb_drive_name("!!!") == "MIDICAPTAIN"
    assert validate_usb_drive_name(123) == "MIDICAPTAIN"


def test_validate_usb_drive_name_whitespace():
    """Test whitespace is stripped and spaces removed."""
    assert validate_usb_drive_name("  MYDEVICE  ") == "MYDEVICE"
    # Internal spaces are also removed (test on line 68 verifies this)
    assert validate_usb_drive_name(" MY DEVICE ") == "MYDEVICE"


def test_get_usb_drive_name_from_config():
    """Test extracting drive name from config dict."""
    cfg = {"usb_drive_name": "CUSTOM"}
    assert get_usb_drive_name(cfg) == "CUSTOM"
    
    cfg = {"usb_drive_name": "my device"}
    assert get_usb_drive_name(cfg) == "MYDEVICE"
    
    cfg = {}
    assert get_usb_drive_name(cfg) == "MIDICAPTAIN"
    
    cfg = {"usb_drive_name": ""}
    assert get_usb_drive_name(cfg) == "MIDICAPTAIN"


def test_get_usb_drive_name_validation():
    """Test get_usb_drive_name applies validation."""
    cfg = {"usb_drive_name": "verylongdevicename"}
    assert get_usb_drive_name(cfg) == "VERYLONGDEV"  # Truncated to 11 chars
    
    cfg = {"usb_drive_name": "MY-DEVICE!@#"}
    assert get_usb_drive_name(cfg) == "MYDEVICE"


# ── dev_mode tests ────────────────────────────────────────────────────────────

def test_get_dev_mode_default_false():
    """dev_mode defaults to False when absent from config."""
    assert get_dev_mode({}) is False


def test_get_dev_mode_explicit_true():
    """dev_mode returns True when set to true."""
    assert get_dev_mode({"dev_mode": True}) is True


def test_get_dev_mode_explicit_false():
    """dev_mode returns False when explicitly set to false."""
    assert get_dev_mode({"dev_mode": False}) is False


def test_get_dev_mode_truthy_values():
    """dev_mode coerces truthy non-bool values to True."""
    assert get_dev_mode({"dev_mode": 1}) is True


def test_get_dev_mode_falsy_values():
    """dev_mode coerces falsy non-bool values to False."""
    assert get_dev_mode({"dev_mode": 0}) is False
    assert get_dev_mode({"dev_mode": None}) is False


# ── midi_thru_usb tests ───────────────────────────────────────────────────────

def test_get_midi_thru_usb_default_true():
    """midi_thru_usb defaults to True when absent from config (back-compat)."""
    assert get_midi_thru_usb({}) is True


def test_get_midi_thru_usb_explicit_true():
    """midi_thru_usb returns True when explicitly set to true."""
    assert get_midi_thru_usb({"midi_thru_usb": True}) is True


def test_get_midi_thru_usb_explicit_false():
    """midi_thru_usb returns False when explicitly set to false."""
    assert get_midi_thru_usb({"midi_thru_usb": False}) is False


def test_get_midi_thru_usb_truthy_values():
    """midi_thru_usb coerces truthy non-bool values to True."""
    assert get_midi_thru_usb({"midi_thru_usb": 1}) is True


def test_get_midi_thru_usb_falsy_values():
    """midi_thru_usb coerces falsy non-bool values to False."""
    assert get_midi_thru_usb({"midi_thru_usb": 0}) is False
    assert get_midi_thru_usb({"midi_thru_usb": None}) is False


# ── midi_thru_din tests ───────────────────────────────────────────────────────

def test_get_midi_thru_din_default_true():
    """midi_thru_din defaults to True when absent from config (back-compat)."""
    assert get_midi_thru_din({}) is True


def test_get_midi_thru_din_explicit_true():
    """midi_thru_din returns True when explicitly set to true."""
    assert get_midi_thru_din({"midi_thru_din": True}) is True


def test_get_midi_thru_din_explicit_false():
    """midi_thru_din returns False when explicitly set to false."""
    assert get_midi_thru_din({"midi_thru_din": False}) is False


def test_get_midi_thru_din_truthy_values():
    """midi_thru_din coerces truthy non-bool values to True."""
    assert get_midi_thru_din({"midi_thru_din": 1}) is True


def test_get_midi_thru_din_falsy_values():
    """midi_thru_din coerces falsy non-bool values to False."""
    assert get_midi_thru_din({"midi_thru_din": 0}) is False
    assert get_midi_thru_din({"midi_thru_din": None}) is False


def test_midi_thru_usb_and_din_independent():
    """Toggles are independent — setting one does not affect the other."""
    assert get_midi_thru_usb({"midi_thru_din": False}) is True
    assert get_midi_thru_din({"midi_thru_usb": False}) is True

