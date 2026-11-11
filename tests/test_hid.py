"""
Tests for HID dispatch logic in firmware/dev/core/hid.py.

Verifies every OEM SuperMode HID action, key, and modifier combination.
Uses mock Keyboard and Mouse objects to record HID report calls.
"""

import sys
import time
import pytest
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.hid import dispatch_hid, KEY_TABLE, MODIFIER_TABLE, _MOUSE_LEFT, _MOUSE_RIGHT
from tests.mocks.adafruit_hid.keyboard import Keyboard
from tests.mocks.adafruit_hid.keycode import Keycode
from tests.mocks.adafruit_hid.mouse import Mouse
from tests.mocks.usb_hid import devices as mock_devices


@pytest.fixture
def kbd():
    kb = Keyboard(mock_devices)
    kb.clear()
    return kb


@pytest.fixture
def mse():
    m = Mouse(mock_devices)
    m.clear()
    return m


# ---------------------------------------------------------------------------
# KEY_TABLE coverage
# ---------------------------------------------------------------------------

class TestKeyTable:
    """Verify KEY_TABLE contains all OEM-specified keys."""

    _OEM_LETTERS = list("abcdefghijklmnopqrstuvwxyz")
    _OEM_DIGITS = list("0123456789")
    _OEM_FUNCTION = [f"f{n}" for n in range(1, 13)]
    _OEM_SPECIAL = [
        "space", "esc", "caps", "right", "left", "up", "down",
        "end", "del", "pageup", "pagedown", "enter", "pause",
        "table", "backspace", "home", "ins", "prints",
    ]
    _OEM_MOUSE = ["mouse_l", "mouse_r"]

    @pytest.mark.parametrize("key", _OEM_LETTERS)
    def test_letter_keys_present(self, key):
        assert key in KEY_TABLE

    @pytest.mark.parametrize("key", _OEM_DIGITS)
    def test_digit_keys_present(self, key):
        assert key in KEY_TABLE

    @pytest.mark.parametrize("key", _OEM_FUNCTION)
    def test_function_keys_present(self, key):
        assert key in KEY_TABLE

    @pytest.mark.parametrize("key", _OEM_SPECIAL)
    def test_special_keys_present(self, key):
        assert key in KEY_TABLE

    @pytest.mark.parametrize("key", _OEM_MOUSE)
    def test_mouse_keys_present(self, key):
        assert key in KEY_TABLE

    def test_mouse_l_is_sentinel(self):
        assert KEY_TABLE["mouse_l"] == _MOUSE_LEFT

    def test_mouse_r_is_sentinel(self):
        assert KEY_TABLE["mouse_r"] == _MOUSE_RIGHT

    def test_keyboard_keys_are_ints(self):
        for name, code in KEY_TABLE.items():
            if code not in (_MOUSE_LEFT, _MOUSE_RIGHT):
                assert isinstance(code, int), f"KEY_TABLE[{name!r}] should be int, got {type(code)}"

    def test_all_keyboard_keycodes_in_valid_range(self):
        for name, code in KEY_TABLE.items():
            if code not in (_MOUSE_LEFT, _MOUSE_RIGHT):
                assert 0x04 <= code <= 0xe7, f"KEY_TABLE[{name!r}] = 0x{code:02x} out of HID keycode range"


class TestModifierTable:
    """Verify MODIFIER_TABLE covers all OEM modifier names."""

    _OEM_MODIFIERS = ["ctrl", "shift", "alt", "option", "windows"]

    @pytest.mark.parametrize("mod", _OEM_MODIFIERS)
    def test_modifier_present(self, mod):
        assert mod in MODIFIER_TABLE

    def test_modifiers_are_modifier_keycodes(self):
        for mod, code in MODIFIER_TABLE.items():
            assert 0xe0 <= code <= 0xe7, f"MODIFIER_TABLE[{mod!r}] = 0x{code:02x} not in modifier range"

    def test_option_equals_alt(self):
        assert MODIFIER_TABLE["option"] == MODIFIER_TABLE["alt"]


# ---------------------------------------------------------------------------
# dispatch_hid — action="send"
# ---------------------------------------------------------------------------

class TestDispatchHidSend:

    def test_send_letter_a(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", "A")
        calls = kbd.get_calls()
        assert len(calls) == 1
        assert calls[0][0] == "send"
        assert KEY_TABLE["a"] in calls[0]

    def test_send_case_insensitive(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", "a")
        dispatch_hid(kbd, mse, "send", "A")
        calls = kbd.get_calls()
        assert calls[0][1] == calls[1][1]  # same keycode

    def test_send_with_ctrl_modifier(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", "S", modifier="ctrl")
        calls = kbd.get_calls()
        assert len(calls) == 1
        assert calls[0][0] == "send"
        assert MODIFIER_TABLE["ctrl"] in calls[0]
        assert KEY_TABLE["s"] in calls[0]

    def test_send_with_shift_modifier(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", "A", modifier="shift")
        calls = kbd.get_calls()
        assert MODIFIER_TABLE["shift"] in calls[0]
        assert KEY_TABLE["a"] in calls[0]

    def test_send_with_option_modifier(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", "F", modifier="option")
        calls = kbd.get_calls()
        assert MODIFIER_TABLE["option"] in calls[0]

    def test_send_with_windows_modifier(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", "D", modifier="windows")
        calls = kbd.get_calls()
        assert MODIFIER_TABLE["windows"] in calls[0]

    def test_send_function_key(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", "F5")
        calls = kbd.get_calls()
        assert KEY_TABLE["f5"] in calls[0]

    def test_send_special_keys(self, kbd, mse):
        for key in ("Space", "Esc", "Enter", "BackSpace", "Table", "Del",
                    "Home", "End", "PageUp", "PageDown", "Ins", "Caps",
                    "PrintS", "Pause", "Up", "Down", "Left", "Right"):
            kbd.clear()
            dispatch_hid(kbd, mse, "send", key)
            assert len(kbd.get_calls()) == 1, f"Expected 1 call for key={key!r}"

    def test_send_digit_keys(self, kbd, mse):
        for digit in "0123456789":
            kbd.clear()
            dispatch_hid(kbd, mse, "send", digit)
            assert len(kbd.get_calls()) == 1, f"Expected 1 call for digit={digit!r}"

    def test_send_unknown_key_is_noop(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", "Nonexistent_Key_XYZ")
        assert kbd.get_calls() == []

    def test_send_none_key_is_noop(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", None)
        assert kbd.get_calls() == []


# ---------------------------------------------------------------------------
# dispatch_hid — action="press" and "release"
# ---------------------------------------------------------------------------

class TestDispatchHidPressRelease:

    def test_press_key(self, kbd, mse):
        dispatch_hid(kbd, mse, "press", "A")
        calls = kbd.get_calls()
        assert calls[0][0] == "press"
        assert KEY_TABLE["a"] in calls[0]

    def test_release_key(self, kbd, mse):
        dispatch_hid(kbd, mse, "release", "A")
        calls = kbd.get_calls()
        assert calls[0][0] == "release"

    def test_press_then_release_cycle(self, kbd, mse):
        dispatch_hid(kbd, mse, "press", "A", modifier="ctrl")
        dispatch_hid(kbd, mse, "release", "A", modifier="ctrl")
        calls = kbd.get_calls()
        assert calls[0][0] == "press"
        assert calls[1][0] == "release"

    def test_release_all_clears_keyboard(self, kbd, mse):
        dispatch_hid(kbd, mse, "press", "A")
        dispatch_hid(kbd, mse, "release", "all")
        calls = kbd.get_calls()
        assert calls[-1][0] == "release_all"


# ---------------------------------------------------------------------------
# dispatch_hid — action="release" with key="all"
# ---------------------------------------------------------------------------

class TestDispatchHidReleaseAll:

    def test_release_all_calls_release_all(self, kbd, mse):
        dispatch_hid(kbd, mse, "release", "all")
        assert kbd.get_calls() == [("release_all",)]

    def test_release_all_case_insensitive(self, kbd, mse):
        dispatch_hid(kbd, mse, "release", "ALL")
        assert kbd.get_calls() == [("release_all",)]

    def test_release_all_with_none_keyboard(self, mse):
        # Should not raise even when keyboard is None
        dispatch_hid(None, mse, "release", "all")


# ---------------------------------------------------------------------------
# dispatch_hid — action="delay"
# ---------------------------------------------------------------------------

class TestDispatchHidDelay:

    def test_delay_no_keyboard_calls(self, kbd, mse, monkeypatch):
        slept = []
        monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
        dispatch_hid(kbd, mse, "delay", None, delay_ms=50)
        assert kbd.get_calls() == []
        assert mse.get_calls() == []

    def test_delay_duration(self, kbd, mse, monkeypatch):
        slept = []
        monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
        dispatch_hid(kbd, mse, "delay", None, delay_ms=100)
        assert len(slept) == 1
        assert abs(slept[0] - 0.1) < 1e-6

    def test_delay_minimum_1ms(self, kbd, mse, monkeypatch):
        slept = []
        monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
        dispatch_hid(kbd, mse, "delay", None, delay_ms=0)
        assert slept[0] >= 0.001


# ---------------------------------------------------------------------------
# dispatch_hid — Mouse buttons
# ---------------------------------------------------------------------------

class TestDispatchHidMouse:

    def test_send_mouse_l(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", "Mouse_L")
        calls = mse.get_calls()
        assert ("press", Mouse.LEFT_BUTTON) in calls
        assert ("release", Mouse.LEFT_BUTTON) in calls

    def test_send_mouse_r(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", "Mouse_R")
        calls = mse.get_calls()
        assert ("press", Mouse.RIGHT_BUTTON) in calls
        assert ("release", Mouse.RIGHT_BUTTON) in calls

    def test_press_mouse_l(self, kbd, mse):
        dispatch_hid(kbd, mse, "press", "Mouse_L")
        assert ("press", Mouse.LEFT_BUTTON) in mse.get_calls()

    def test_release_mouse_r(self, kbd, mse):
        dispatch_hid(kbd, mse, "release", "Mouse_R")
        assert ("release", Mouse.RIGHT_BUTTON) in mse.get_calls()

    def test_mouse_does_not_trigger_keyboard(self, kbd, mse):
        dispatch_hid(kbd, mse, "send", "Mouse_L")
        assert kbd.get_calls() == []

    def test_mouse_none_is_noop(self, kbd):
        # Should not raise
        dispatch_hid(kbd, None, "send", "Mouse_L")


# ---------------------------------------------------------------------------
# dispatch_hid — None keyboard/mouse edge cases
# ---------------------------------------------------------------------------

class TestDispatchHidNoneHardware:

    def test_keyboard_none_is_noop_for_keyboard_key(self, mse):
        dispatch_hid(None, mse, "send", "A")  # should not raise

    def test_both_none_is_noop(self):
        dispatch_hid(None, None, "send", "A")  # should not raise

    def test_delay_works_without_hardware(self, monkeypatch):
        slept = []
        monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
        dispatch_hid(None, None, "delay", None, delay_ms=10)
        assert len(slept) == 1
