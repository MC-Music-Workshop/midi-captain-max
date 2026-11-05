"""
Pytest configuration and fixtures for MIDI Captain tests.

This file sets up the mock modules before any firmware code is imported.
"""

import sys
from pathlib import Path

# Add tests/mocks to the path so we can import our mock modules
TESTS_DIR = Path(__file__).parent
MOCKS_DIR = TESTS_DIR / "mocks"


def install_mocks():
    """Install mock modules into sys.modules before importing firmware code."""
    from tests.mocks import board, digitalio, neopixel, displayio, busio
    from tests.mocks import usb_midi, rotaryio, analogio, terminalio
    from tests.mocks import usb_hid
    from tests.mocks.adafruit_hid import keyboard as hid_keyboard_mock
    from tests.mocks.adafruit_hid import keycode as hid_keycode_mock
    from tests.mocks.adafruit_hid import mouse as hid_mouse_mock
    
    sys.modules["board"] = board
    sys.modules["digitalio"] = digitalio
    sys.modules["neopixel"] = neopixel
    sys.modules["displayio"] = displayio
    sys.modules["busio"] = busio
    sys.modules["usb_midi"] = usb_midi
    sys.modules["rotaryio"] = rotaryio
    sys.modules["analogio"] = analogio
    sys.modules["terminalio"] = terminalio
    sys.modules["usb_hid"] = usb_hid

    # adafruit_hid — use mock package that records calls but shares real Keycode constants
    import types as _types
    hid_pkg = _types.ModuleType("adafruit_hid")
    sys.modules["adafruit_hid"] = hid_pkg
    sys.modules["adafruit_hid.keyboard"] = hid_keyboard_mock
    sys.modules["adafruit_hid.keycode"] = hid_keycode_mock
    sys.modules["adafruit_hid.mouse"] = hid_mouse_mock
    
    # Mock additional CircuitPython modules that may be needed
    # These are stub modules for imports that we don't need to fully mock
    
    class StubModule:
        def __getattr__(self, name):
            return StubModule()
        def __call__(self, *args, **kwargs):
            return StubModule()
    
    # Adafruit libraries that need stubs
    sys.modules["adafruit_display_text"] = StubModule()
    sys.modules["adafruit_display_text.label"] = StubModule()
    sys.modules["adafruit_bitmap_font"] = StubModule()
    sys.modules["adafruit_bitmap_font.bitmap_font"] = StubModule()
    sys.modules["adafruit_st7789"] = StubModule()
    sys.modules["adafruit_midi"] = StubModule()
    sys.modules["adafruit_midi.control_change"] = StubModule()
    sys.modules["adafruit_midi.program_change"] = StubModule()
    sys.modules["adafruit_midi.note_on"] = StubModule()
    sys.modules["adafruit_midi.note_off"] = StubModule()


# Install mocks at import time (before tests run)
install_mocks()


# Fixtures
import pytest


@pytest.fixture
def boot(monkeypatch, tmp_path):
    """Boot the real firmware/dev/code.py on desktop mocks: `pedal = boot(cfg)`.

    Returns a tests.firmware_harness.Pedal (press/tap/hold switches, read sent MIDI,
    LEDs and serial output, index code.py globals). See tests/firmware_harness.py.
    """
    from tests.firmware_harness import boot_pedal
    return lambda cfg: boot_pedal(cfg, monkeypatch, tmp_path)


@pytest.fixture
def mock_board():
    """Provide access to mock board module."""
    from tests.mocks import board
    return board


@pytest.fixture
def mock_neopixel():
    """Provide a fresh NeoPixel instance for testing."""
    from tests.mocks.neopixel import NeoPixel
    from tests.mocks.board import GP7
    return NeoPixel(GP7, 30)


@pytest.fixture
def mock_switches():
    """Provide mock switch inputs for testing."""
    from tests.mocks.digitalio import DigitalInOut, Direction, Pull
    from tests.mocks import board
    
    switch_pins = [
        board.GP0, board.GP1, board.GP25, board.GP24, board.GP23,
        board.GP20, board.GP9, board.GP10, board.GP11, board.GP18, board.GP19
    ]
    
    switches = []
    for pin in switch_pins:
        sw = DigitalInOut(pin)
        sw.direction = Direction.INPUT
        sw.pull = Pull.UP
        switches.append(sw)
    
    return switches


@pytest.fixture
def sample_config():
    """Provide a sample configuration dict."""
    return {
        "buttons": [
            {"label": "1", "cc": 20, "color": "red"},
            {"label": "2", "cc": 21, "color": "green"},
            {"label": "3", "cc": 22, "color": "blue"},
            {"label": "4", "cc": 23, "color": "yellow"},
            {"label": "Down", "cc": 24, "color": "cyan"},
            {"label": "A", "cc": 25, "color": "magenta"},
            {"label": "B", "cc": 26, "color": "orange"},
            {"label": "C", "cc": 27, "color": "purple"},
            {"label": "D", "cc": 28, "color": "white"},
            {"label": "Up", "cc": 29, "color": "red"},
        ]
    }
