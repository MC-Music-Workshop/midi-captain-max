"""
HID (keyboard/mouse) dispatch for MIDI Captain firmware.

Implements keyboard and mouse simulation matching OEM SuperMode HID specification.

Key names follow OEM SuperMode conventions (case-insensitive matching):
  A-Z, 0-9, F1-F12
  Mouse_L, Mouse_R
  Space, Esc, Caps, Right, Left, Up, Down, End, Del
  PageUp, PageDown, Enter, Pause, Table (=Tab), BackSpace, Home, Ins, PrintS
  all  (used with action='release' to release all held keys)

Modifier names (lowercase, per config schema):
  ctrl, shift, alt, option (=Alt/macOS Option), windows (=GUI/Meta)

Actions:
  send    -- press + release immediately (default)
  press   -- hold key (must be paired with a release to avoid stuck keys)
  release -- release a specific key, or all keys if hid_key='all'
  delay   -- block for hid_delay_ms milliseconds

Design note -- single action per call:
  dispatch_hid() executes exactly one HID action per invocation.  This matches
  the current firmware architecture where each button press triggers one action.
  When multi-action-per-press support is added in a future release, the call site
  in handle_switches() should iterate a list of action dicts and call
  dispatch_hid() once per item, keeping this function signature stable.

Author: Max Cascone
Date: 2026-04-28
"""

import time

# ---------------------------------------------------------------------------
# Mouse sentinel constants -- used in KEY_TABLE to distinguish mouse buttons
# from keyboard keycodes so the dispatch function can route them correctly.
# ---------------------------------------------------------------------------
_MOUSE_LEFT = "MOUSE_LEFT"
_MOUSE_RIGHT = "MOUSE_RIGHT"

# Mouse button bitmasks (USB HID spec, constant across all HID implementations).
# Hardcoded here to avoid a dynamic import inside the hot dispatch path,
# which would trigger a filesystem scan on every button press in CP 7.x.
_MOUSE_BTN_LEFT = 0x01
_MOUSE_BTN_RIGHT = 0x02
_MOUSE_BTN_MIDDLE = 0x04

# ---------------------------------------------------------------------------
# Key name table -- maps OEM key name strings to USB HID keycodes.
# Case-insensitive lookup is applied at dispatch time (key.lower()).
# Mouse buttons are mapped to sentinel strings, not keycodes.
# ---------------------------------------------------------------------------
# All keycodes follow USB HID Usage Tables (Usage Page 0x01, Keyboard/Keypad).
KEY_TABLE = {
    # Letters (0x04-0x1d)
    "a": 0x04, "b": 0x05, "c": 0x06, "d": 0x07, "e": 0x08,
    "f": 0x09, "g": 0x0a, "h": 0x0b, "i": 0x0c, "j": 0x0d,
    "k": 0x0e, "l": 0x0f, "m": 0x10, "n": 0x11, "o": 0x12,
    "p": 0x13, "q": 0x14, "r": 0x15, "s": 0x16, "t": 0x17,
    "u": 0x18, "v": 0x19, "w": 0x1a, "x": 0x1b, "y": 0x1c, "z": 0x1d,
    # Digits (0x1e-0x27)
    "1": 0x1e, "2": 0x1f, "3": 0x20, "4": 0x21, "5": 0x22,
    "6": 0x23, "7": 0x24, "8": 0x25, "9": 0x26, "0": 0x27,
    # Special keys
    "enter": 0x28,
    "esc": 0x29,
    "backspace": 0x2a,
    "table": 0x2b,      # OEM calls the Tab key "Table"
    "space": 0x2c,
    "caps": 0x39,       # Caps Lock
    # Function keys (0x3a-0x45)
    "f1": 0x3a, "f2": 0x3b, "f3": 0x3c, "f4": 0x3d,
    "f5": 0x3e, "f6": 0x3f, "f7": 0x40, "f8": 0x41,
    "f9": 0x42, "f10": 0x43, "f11": 0x44, "f12": 0x45,
    # Navigation/editing
    "prints": 0x46,     # Print Screen
    "pause": 0x48,
    "ins": 0x49,        # Insert
    "home": 0x4a,
    "pageup": 0x4b,
    "del": 0x4c,        # Delete
    "end": 0x4d,
    "pagedown": 0x4e,
    # Arrow keys
    "right": 0x4f,
    "left": 0x50,
    "down": 0x51,
    "up": 0x52,
    # Mouse buttons (sentinel values -- routed to Mouse, not Keyboard)
    "mouse_l": _MOUSE_LEFT,
    "mouse_r": _MOUSE_RIGHT,
}

# ---------------------------------------------------------------------------
# Modifier key table -- maps config modifier names to USB HID keycodes.
# Modifier keycodes (0xe0-0xe7) are detected by adafruit_hid Keyboard and
# routed to the modifier byte of the HID report rather than a key slot.
# ---------------------------------------------------------------------------
MODIFIER_TABLE = {
    "ctrl": 0xe0,     # Left Ctrl
    "shift": 0xe1,    # Left Shift
    "alt": 0xe2,      # Left Alt
    "option": 0xe2,   # macOS Option = Left Alt
    "windows": 0xe3,  # Left GUI (Windows / Meta)
}


def dispatch_hid(keyboard, mouse, action, key, modifier=None, delay_ms=50):
    """Execute a single HID action.

    Args:
        keyboard: adafruit_hid Keyboard object, or None if HID not available.
        mouse:    adafruit_hid Mouse object, or None if HID not available.
        action:   "send", "press", "release", or "delay".
        key:      OEM key name string (case-insensitive), or "all" for release-all.
                  Ignored when action == "delay".
        modifier: Optional modifier name ("ctrl", "shift", "alt", "option", "windows").
                  Applied for "send", "press" and "release" (release lets go of
                  the modifier too). Ignored for mouse buttons and "delay".
        delay_ms: Delay in milliseconds, used only when action == "delay".

    Returns:
        None.  Silently ignores unknown keys and unavailable hardware.
    """
    if action == "delay":
        time.sleep(max(1, delay_ms) / 1000.0)
        return

    if key is None:
        return

    # Handle release-all before key lookup
    if action == "release" and key.lower() == "all":
        if keyboard is not None:
            keyboard.release_all()
        if mouse is not None:
            try:
                mouse.release(_MOUSE_BTN_LEFT | _MOUSE_BTN_RIGHT | _MOUSE_BTN_MIDDLE)
            except Exception:
                pass
        return

    # Look up key code (case-insensitive)
    keycode = KEY_TABLE.get(key.lower())
    if keycode is None:
        return

    # Route mouse buttons
    if keycode in (_MOUSE_LEFT, _MOUSE_RIGHT):
        if mouse is None:
            return
        button = _MOUSE_BTN_LEFT if keycode == _MOUSE_LEFT else _MOUSE_BTN_RIGHT
        try:
            if action == "send":
                mouse.press(button)
                mouse.release(button)
            elif action == "press":
                mouse.press(button)
            elif action == "release":
                mouse.release(button)
        except Exception:
            pass
        return

    # Keyboard key
    if keyboard is None:
        return

    try:
        # Resolve optional modifier keycode
        mod_keycode = None
        if modifier:
            mod_keycode = MODIFIER_TABLE.get(modifier.lower())

        if action == "send":
            if mod_keycode is not None:
                keyboard.send(mod_keycode, keycode)
            else:
                keyboard.send(keycode)

        elif action == "press":
            if mod_keycode is not None:
                keyboard.press(mod_keycode, keycode)
            else:
                keyboard.press(keycode)

        elif action == "release":
            if mod_keycode is not None:
                keyboard.release(mod_keycode, keycode)
            else:
                keyboard.release(keycode)
    except Exception:
        pass
