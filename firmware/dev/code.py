"""
MIDI Captain MAX Custom Firmware - MVP

Config-driven, bidirectional MIDI firmware for Paint Audio MIDI Captain controllers.

Features:
- JSON configuration for button labels, CC numbers, and colors
- Bidirectional MIDI: host controls LED/display state, device sends switch/encoder events
- Toggle mode: local state for instant feedback, host override when it speaks
- Automatic device detection (STD10 vs Mini6 based on hardware probing)

Hardware Variants:
- STD10: 10 switches, encoder, 2 expression inputs, ST7789 display, 30 NeoPixels
- Mini6: 6 switches, ST7789 display, 18 NeoPixels
- NANO4: 4 switches, ST7789 display, 12 NeoPixels
- DUO2: 2 switches, segmented LCD (no display support), 6 NeoPixels
- ONE1: 1 switch, segmented LCD (no display support), 3 NeoPixels

Author: Max Cascone (based on work by Helmut Keller)
Date: 2026-01-27
"""

print("\n=== MIDI CAPTAIN MAX ===\n")

import board
import neopixel
import time
import digitalio
import usb_midi
import busio
import rotaryio
import json
from analogio import AnalogIn
import adafruit_midi
from adafruit_midi.control_change import ControlChange
from adafruit_midi.program_change import ProgramChange
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
# Imported to register the SysEx message type so receive() parses incoming
# F0...F7 and MIDI thru can forward it; not dispatched locally.
from adafruit_midi.system_exclusive import SystemExclusive

# Import core modules (testable logic)
from core.colors import COLORS, get_color, dim_color, rgb_to_hex, get_off_color, get_off_color_for_display, compute_keytimes_led_color
from core.config import (
    load_config as _load_config_from_file,
    validate_config,
    get_active_page,
    get_display_config,
    get_button_state_config,
    get_long_press_threshold_ms,
    get_midi_thru_usb_to_din,
    get_midi_thru_din_to_usb,
    get_midi_thru_din_to_din,
    get_midi_thru_usb_to_usb,
    get_dev_mode,
)
from core.button import Switch, ButtonState, KeytimesButtonState, dispatch_keytimes_events
from core.hid import dispatch_hid

# =============================================================================
# Font Size Configuration
# =============================================================================
#
# Maps descriptive size names to font files and approximate heights.
# - "small": terminalio.FONT (built-in, ~8px) - compact button labels
# - "medium": PTSans-Regular-20.pcf (~20px) - readable status text
# - "large": PTSans-Bold-60.pcf (~60px) - large, bold display
#
FONT_SIZE_MAP = {
    "small": ("terminalio", 8),
    "medium": ("/fonts/PTSans-Regular-20.pcf", 20),
    "large": ("/fonts/PTSans-Bold-60.pcf", 60),
}

# =============================================================================
# Device Detection
# =============================================================================
#
# Two-tier detection strategy:
#   1. Config-based: read "device" field from /config.json (most reliable)
#   2. Hardware probe: check STD10-exclusive switch pins GP0/GP18/GP19/GP20
#
# The old approach (probing board.LED / board.VBUS_SENSE for Mini6) was broken
# because GP25 (board.LED) is also a switch pin on STD10, so both devices
# passed the probe and everything was detected as Mini6.
#
# Config loading priority:
#   1. /config.json if present (user customization - always wins)
#   2. /config-{device}.json (device-specific defaults)
#   3. Built-in fallback defaults
#
# =============================================================================


def _read_device_from_config():
    """Quick config.json read for just the device field.

    Returns "one1", "duo2", "nano4", "mini6", "std10", or None if not found/invalid.
    """
    try:
        with open("/config.json", "r") as f:
            device = json.load(f).get("device")
            if device in ("one1", "duo2", "nano4", "mini6", "std10"):
                return device
    except Exception:
        pass
    return None


def _probe_hardware():
    """Detect device type by probing STD10-exclusive switch pins.

    STD10 has physical switches on GP0 (encoder push), GP18 (switch D),
    GP19 (switch Up), GP20 (switch Down). Mini6 does not use these pins.
    With internal pull-ups, connected switches read HIGH when open.

    Returns "std10" if 3+ of 4 pins read HIGH, otherwise "mini6".
    """
    probe_pins = [board.GP0, board.GP18, board.GP19, board.GP20]
    count = 0
    for pin in probe_pins:
        try:
            t = digitalio.DigitalInOut(pin)
            t.direction = digitalio.Direction.INPUT
            t.pull = digitalio.Pull.UP
            if t.value:
                count += 1
            t.deinit()
        except Exception:
            pass
    return "std10" if count >= 3 else "mini6"


def detect_device_type():
    """Auto-detect device type.

    Priority:
      1. Explicit "device" field in /config.json
      2. Hardware pin probing (STD10-exclusive pins)
    """
    device = _read_device_from_config()
    if device:
        print(f"Device type from config: {device}")
        return device

    device = _probe_hardware()
    print(f"Device type from hardware probe: {device}")
    return device


# Detect device first, before loading any config
DETECTED_DEVICE = detect_device_type()
print(f"Hardware detected: {DETECTED_DEVICE}")

# Now load appropriate device module
if DETECTED_DEVICE == "one1":
    from devices.one1 import (
        LED_PIN, LED_COUNT, SWITCH_PINS, switch_to_led,
        ENCODER_A_PIN, ENCODER_B_PIN, EXP1_PIN, EXP2_PIN, BATTERY_PIN,
        SEG_DISPLAY_TX_PIN, SEG_DISPLAY_RX_PIN, SEG_DISPLAY_BAUDRATE,
        SEG_DISPLAY_HEADER, SEG_DISPLAY_FOOTER,
        SEG_DISPLAY_DELAY_MS, SEG_DISPLAY_REPEATS
    )
    TFT_DC_PIN = None
    BUTTON_COUNT = 1
    HAS_ENCODER = False
    HAS_EXPRESSION = False
elif DETECTED_DEVICE == "duo2":
    from devices.duo2 import (
        LED_PIN, LED_COUNT, SWITCH_PINS, switch_to_led,
        ENCODER_A_PIN, ENCODER_B_PIN, EXP1_PIN, EXP2_PIN, BATTERY_PIN,
        SEG_DISPLAY_TX_PIN, SEG_DISPLAY_RX_PIN, SEG_DISPLAY_BAUDRATE,
        SEG_DISPLAY_HEADER, SEG_DISPLAY_FOOTER,
        SEG_DISPLAY_DELAY_MS, SEG_DISPLAY_REPEATS
    )
    TFT_DC_PIN = None
    BUTTON_COUNT = 2
    HAS_ENCODER = False
    HAS_EXPRESSION = False
elif DETECTED_DEVICE == "nano4":
    from devices.nano4 import (
        LED_PIN, LED_COUNT, SWITCH_PINS, switch_to_led,
        TFT_DC_PIN, TFT_CS_PIN, TFT_SCK_PIN, TFT_MOSI_PIN,
        DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_ROWSTART, DISPLAY_ROTATION,
        ENCODER_A_PIN, ENCODER_B_PIN, EXP1_PIN, EXP2_PIN, BATTERY_PIN
    )
    SEG_DISPLAY_TX_PIN = None
    BUTTON_COUNT = 4
    HAS_ENCODER = False
    HAS_EXPRESSION = False
elif DETECTED_DEVICE == "mini6":
    from devices.mini6 import (
        LED_PIN, LED_COUNT, SWITCH_PINS, switch_to_led,
        TFT_DC_PIN, TFT_CS_PIN, TFT_SCK_PIN, TFT_MOSI_PIN,
        DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_ROWSTART, DISPLAY_ROTATION,
        ENCODER_A_PIN, ENCODER_B_PIN, EXP1_PIN, EXP2_PIN, BATTERY_PIN
    )
    SEG_DISPLAY_TX_PIN = None
    BUTTON_COUNT = 6
    HAS_ENCODER = False
    HAS_EXPRESSION = False
else:
    # Default to STD10
    from devices.std10 import (
        LED_PIN, LED_COUNT, SWITCH_PINS, switch_to_led,
        TFT_DC_PIN, TFT_CS_PIN, TFT_SCK_PIN, TFT_MOSI_PIN,
        DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_ROWSTART, DISPLAY_ROTATION,
        ENCODER_A_PIN, ENCODER_B_PIN, EXP1_PIN, EXP2_PIN, BATTERY_PIN
    )
    SEG_DISPLAY_TX_PIN = None
    BUTTON_COUNT = 10
    HAS_ENCODER = True
    HAS_EXPRESSION = True

# Derive display type flags from hardware constants
HAS_TFT = TFT_DC_PIN is not None
HAS_SEG_DISPLAY = SEG_DISPLAY_TX_PIN is not None

DEVICE_TYPE = DETECTED_DEVICE  # For compatibility

# =============================================================================
# Version
# =============================================================================


def _read_version():
    try:
        with open("/VERSION.txt", "r") as f:
            return f.read().strip()
    except Exception:
        return "dev"


VERSION = _read_version()
print(f"Version: {VERSION}")

# =============================================================================
# Color Palette - imported from core/colors.py
# =============================================================================
# COLORS, get_color, dim_color, rgb_to_hex, get_off_color imported at top

# =============================================================================
# Configuration
# =============================================================================


def load_config():
    """Load button configuration from JSON file.

    Priority:
      1. /config.json (user customization - always wins)
      2. /config-{device}.json (device-specific defaults)
      3. Built-in fallback defaults
    """
    # Try user config. _load_config_from_file normalizes to the pages shape, so
    # "did we load a real config" is "does the active page have buttons".
    cfg = _load_config_from_file("/config.json", button_count=BUTTON_COUNT)
    if len(get_active_page(cfg).get("buttons", [])) > 0:
        print("Loaded config.json")
        return validate_config(cfg, button_count=BUTTON_COUNT)

    # Try device-specific default
    device_config = f"/config-{DETECTED_DEVICE}.json"
    cfg = _load_config_from_file(device_config, button_count=BUTTON_COUNT)
    if len(get_active_page(cfg).get("buttons", [])) > 0:
        print(f"Loaded {device_config}")
        return validate_config(cfg, button_count=BUTTON_COUNT)

    # Built-in fallback
    print("No config found, using built-in defaults")
    return validate_config({
        "buttons": [
            {"label": str(i + 1), "cc": 20 + i, "color": "white"}
            for i in range(BUTTON_COUNT)
        ]
    }, button_count=BUTTON_COUNT)


config = load_config()
# Per-page state is initialized by switch_page() at boot; placeholders until then.
active_page = {}
buttons = []

# MIDI Thru routing matrix (read once at boot).
# Cross routes default True; USB->USB defaults False (host loopback risk).
MIDI_THRU_USB_TO_DIN = get_midi_thru_usb_to_din(config)
MIDI_THRU_DIN_TO_USB = get_midi_thru_din_to_usb(config)
MIDI_THRU_DIN_TO_DIN = get_midi_thru_din_to_din(config)
MIDI_THRU_USB_TO_USB = get_midi_thru_usb_to_usb(config)
print(f"MIDI thru: USB->DIN={MIDI_THRU_USB_TO_DIN}, DIN->USB={MIDI_THRU_DIN_TO_USB}, DIN->DIN={MIDI_THRU_DIN_TO_DIN}, USB->USB={MIDI_THRU_USB_TO_USB}")

# =============================================================================
# Fonts
# =============================================================================


if HAS_TFT:
    import displayio
    from adafruit_display_text import label
    from adafruit_bitmap_font import bitmap_font
    import terminalio
    from adafruit_st7789 import ST7789


def load_font(size_name):
    """Load a font based on size name, with fallback to terminalio.

    Args:
        size_name: One of "small", "medium", "large"

    Returns:
        Tuple of (font_object, approximate_height_px)
    """
    if size_name not in FONT_SIZE_MAP:
        print(f"Invalid font size '{size_name}', using 'small'")
        size_name = "small"

    font_path, height = FONT_SIZE_MAP[size_name]

    if font_path == "terminalio":
        return terminalio.FONT, height

    try:
        loaded_font = bitmap_font.load_font(font_path)
        print(f"Loaded font: {font_path} (~{height}px)")
        return loaded_font, height
    except Exception as e:
        print(f"Font load failed for '{font_path}': {e}, falling back to terminalio")
        return terminalio.FONT, 8


if HAS_TFT:
    # Load display config
    display_config = get_display_config(config)
    button_text_size = display_config["button_text_size"]
    status_text_size = display_config["status_text_size"]
    expression_text_size = display_config["expression_text_size"]

    print(f"Display config: button={button_text_size}, status={status_text_size}, expression={expression_text_size}")

    # Load fonts based on config
    BUTTON_FONT, BUTTON_FONT_HEIGHT = load_font(button_text_size)
    STATUS_FONT, STATUS_FONT_HEIGHT = load_font(status_text_size)
    EXPRESSION_FONT, EXPRESSION_FONT_HEIGHT = load_font(expression_text_size)

# =============================================================================
# Hardware Init
# =============================================================================

# NeoPixels
pixels = neopixel.NeoPixel(LED_PIN, LED_COUNT, brightness=0.3, auto_write=False)

# Display — TFT
if HAS_TFT:
    displayio.release_displays()
    spi = busio.SPI(clock=TFT_SCK_PIN, MOSI=TFT_MOSI_PIN)
    display_bus = displayio.FourWire(spi, command=TFT_DC_PIN, chip_select=TFT_CS_PIN)
    display = ST7789(
        display_bus,
        width=DISPLAY_WIDTH,
        height=DISPLAY_HEIGHT,
        rowstart=DISPLAY_ROWSTART,
        rotation=DISPLAY_ROTATION,
    )

# =============================================================================
# Switch Class - imported from core.button
# =============================================================================
# Switch class imported at top from core.button

# Initialize switches
switches = [Switch(pin) for pin in SWITCH_PINS]
print(f"Initialized {len(switches)} switches")

# Encoder (STD10 only)
if HAS_ENCODER:
    encoder = rotaryio.IncrementalEncoder(ENCODER_A_PIN, ENCODER_B_PIN, divisor=2)
    encoder_last_pos = 0
else:
    encoder = None
    encoder_last_pos = 0

# Will be set after config is loaded
encoder_value = 0
encoder_push_state = False  # For toggle mode

# Expression pedals (STD10 only)
if HAS_EXPRESSION:
    exp1 = AnalogIn(EXP1_PIN)
    exp2 = AnalogIn(EXP2_PIN)
    battery = AnalogIn(BATTERY_PIN)
    # Expression pedal calibration (auto-calibrates during use)
    exp1_min, exp1_max = 2048, 63488
    exp2_min, exp2_max = 2048, 63488
    exp1_last, exp2_last = 0, 0
else:
    exp1 = exp2 = battery = None
    exp1_min = exp1_max = exp1_last = 0
    exp2_min = exp2_max = exp2_last = 0

# Battery voltage low-pass filter
vbat_filtered = 0.0
vbat_alpha = 0.01

# =============================================================================
# MIDI Setup
# =============================================================================

midi = adafruit_midi.MIDI(
    midi_in=usb_midi.ports[0],
    midi_out=usb_midi.ports[1],
    in_channel=None,  # receive on all channels; per-button channel filtering done in handle_midi()
    out_channel=0,    # default TX channel (overridden per-message via midi.send(..., channel=X))
    in_buf_size=64,
)
print("USB MIDI initialized")

# 5-pin DIN MIDI via UART (GP16=TX, GP17=RX, 31250 baud)
try:
    _uart = busio.UART(tx=board.GP16, rx=board.GP17, baudrate=31250, timeout=0.003,
                       receiver_buffer_size=64)
    midi_serial = adafruit_midi.MIDI(midi_in=_uart, midi_out=_uart,
                                     in_channel=None, out_channel=0, in_buf_size=64)
    print("5-pin DIN MIDI initialized")
except Exception as e:
    midi_serial = None
    print(f"5-pin DIN MIDI init failed: {e}")


def midi_send(msg, channel=None):
    """Send a MIDI message on both USB and 5-pin DIN simultaneously."""
    midi.send(msg, channel=channel)
    if midi_serial is not None:
        midi_serial.send(msg, channel=channel)

# =============================================================================
# USB HID Setup (Keyboard + Mouse)
# =============================================================================
# HID is only enabled if boot.py called usb_hid.enable(), which happens only
# when at least one button is configured with type="hid".

hid_keyboard = None
hid_mouse = None

try:
    import usb_hid
    if usb_hid.devices:
        from adafruit_hid.keyboard import Keyboard
        from adafruit_hid.mouse import Mouse
        try:
            hid_keyboard = Keyboard(usb_hid.devices)
            print("USB HID Keyboard initialized")
        except Exception as _e:
            print(f"HID Keyboard init failed: {_e}")
        try:
            hid_mouse = Mouse(usb_hid.devices)
            print("USB HID Mouse initialized")
        except Exception as _e:
            print(f"HID Mouse init failed: {_e}")
except Exception:
    pass  # usb_hid not available — no HID buttons in config

# Encoder/expression config — placeholders; switch_page() sets real values at boot.
enc_config = {}
enc_push_config = {}
CC_ENCODER = 11
CC_ENCODER_PUSH = 14
ENC_MIN = 0
ENC_MAX = 127
ENC_INITIAL = 64
ENC_ENABLED = False
ENC_PUSH_ENABLED = False
ENC_PUSH_MODE = "momentary"
ENC_CHANNEL = 0
ENC_PUSH_CHANNEL = 0
ENC_PUSH_CC_ON = 127
ENC_PUSH_CC_OFF = 0
ENC_STEPS = None

exp_config = {}
exp1_config = {"enabled": True, "cc": 12, "label": "EXP1", "min": 0, "max": 127, "polarity": "normal", "threshold": 2}
exp2_config = {"enabled": True, "cc": 13, "label": "EXP2", "min": 0, "max": 127, "polarity": "normal", "threshold": 2}
CC_EXP1 = 12
CC_EXP2 = 13
EXP1_CHANNEL = 0
EXP2_CHANNEL = 0

# =============================================================================
# State
# =============================================================================

# button_states and keytimes_states are placeholders; switch_page() builds real lists at boot.
button_states = []
keytimes_states = []

pc_values = [0] * 16                 # Current PC value per MIDI channel (0-15), shared across all pc_inc/pc_dec buttons
pc_flash_timers = [0.0] * BUTTON_COUNT  # Expiry time (monotonic) for PC button flash; 0 = inactive
hid_flash_timers = [0.0] * BUTTON_COUNT  # Same for HID buttons
PC_FLASH_DURATION_MS = 200              # Default PC/HID button flash duration in ms

encoder_value = ENC_INITIAL  # placeholder; switch_page() sets to per-page ENC_INITIAL
encoder_slot = -1

# =============================================================================
# Display Setup
# =============================================================================

button_labels = []
button_boxes = []
status_label = None
exp1_label = None
exp2_label = None

if HAS_TFT:
    main_group = displayio.Group()

    # Background
    bg_bitmap = displayio.Bitmap(240, 240, 1)
    bg_palette = displayio.Palette(1)
    bg_palette[0] = 0x000000
    bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette, x=0, y=0)
    main_group.append(bg_sprite)

    # Auto-size button height based on font
    button_height = BUTTON_FONT_HEIGHT + 10  # 10px padding

    if BUTTON_COUNT == 4:
        # NANO4: 2 buttons per row, widest spacing
        button_width = 100
        button_spacing = 120
        row_size = 2
    elif BUTTON_COUNT == 6:
        # Mini6: 3 buttons per row, wider spacing
        button_width = 70
        button_spacing = 80
        row_size = 3
    else:
        # STD10: 5 buttons per row
        button_width = 46
        button_spacing = 48
        row_size = 5

    # Adjust row positions to center vertically based on button height
    top_row_y = 5
    bottom_row_y = 240 - button_height - 5

    for i in range(BUTTON_COUNT):
        btn_config = buttons[i] if i < len(buttons) else {"label": str(i + 1), "color": "white"}

        if i < row_size:
            x = 1 + i * button_spacing
            y = top_row_y
        else:
            x = 1 + (i - row_size) * button_spacing
            y = bottom_row_y

        color_rgb = get_color(btn_config.get("color", "white"))
        off_mode = btn_config.get("off_mode", "dim")  # "dim" or "off"
        off_color = get_off_color_for_display(color_rgb, off_mode)

        # Create box background with border
        box_bitmap = displayio.Bitmap(button_width, button_height, 2)
        box_palette = displayio.Palette(2)
        box_palette[0] = 0x000000
        box_palette[1] = rgb_to_hex(off_color)  # Start in off state

        for bx in range(button_width):
            box_bitmap[bx, 0] = 1
            box_bitmap[bx, button_height - 1] = 1
        for by in range(button_height):
            box_bitmap[0, by] = 1
            box_bitmap[button_width - 1, by] = 1

        box_sprite = displayio.TileGrid(box_bitmap, pixel_shader=box_palette, x=x, y=y)
        button_boxes.append((box_sprite, box_palette))
        main_group.append(box_sprite)

        # Label
        lbl = label.Label(
            BUTTON_FONT,
            text=btn_config.get("label", str(i + 1))[:6],
            color=rgb_to_hex(off_color),
            anchor_point=(0.5, 0.5),
            anchored_position=(x + button_width // 2, y + button_height // 2),
        )
        button_labels.append(lbl)
        main_group.append(lbl)

    # Status area (center)
    status_label = label.Label(
        STATUS_FONT,
        text="Ready",
        color=0xFFFFFF,
        anchor_point=(0.5, 0.5),
        anchored_position=(120, 120),
    )
    main_group.append(status_label)

    # Expression pedal display (below status, only if device has expression)
    if HAS_EXPRESSION:
        exp1_lbl_text = exp1_config.get("label", "EXP1")
        exp1_label = label.Label(
            EXPRESSION_FONT,
            text=f"{exp1_lbl_text}: ---",
            color=0x888888,
            anchor_point=(0.5, 0.5),
            anchored_position=(70, 150),
        )
        main_group.append(exp1_label)

        exp2_lbl_text = exp2_config.get("label", "EXP2")
        exp2_label = label.Label(
            EXPRESSION_FONT,
            text=f"{exp2_lbl_text}: ---",
            color=0x888888,
            anchor_point=(0.5, 0.5),
            anchored_position=(170, 150),
        )
        main_group.append(exp2_label)

    display.show(main_group)

# Segmented LCD display
if HAS_SEG_DISPLAY:
    _seg_uart = busio.UART(SEG_DISPLAY_TX_PIN, SEG_DISPLAY_RX_PIN,
                           baudrate=SEG_DISPLAY_BAUDRATE, timeout=0.1)
    _SEG_DIGITS = [0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F]

    def _seg_display_number(n):
        """Send a number (0-999) to the 3-digit 7-segment display."""
        n = max(0, min(999, int(n)))
        d1 = _SEG_DIGITS[(n // 100) % 10] if n >= 100 else 0x00
        d2 = _SEG_DIGITS[(n // 10) % 10] if n >= 10 else 0x00
        d3 = _SEG_DIGITS[n % 10]
        frame = bytes([SEG_DISPLAY_HEADER, d1, d2, d3, SEG_DISPLAY_FOOTER])
        for _ in range(SEG_DISPLAY_REPEATS):
            _seg_uart.write(frame)
            time.sleep(SEG_DISPLAY_DELAY_MS / 1000.0)

    def _seg_boot_animation():
        """Chase outer segments around all digits, mimicking the power-on LCD dance."""
        # Clockwise: top, top-right, bottom-right, bottom, bottom-left, top-left
        outer_segs = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20]
        for _ in range(3):
            for seg in outer_segs:
                _seg_uart.write(bytes([SEG_DISPLAY_HEADER, seg, seg, seg, SEG_DISPLAY_FOOTER]))
                time.sleep(0.07)
        _seg_uart.write(bytes([SEG_DISPLAY_HEADER, 0x00, 0x00, 0x00, SEG_DISPLAY_FOOTER]))

    print("Seg display initialized (GP4/GP5, 9600 baud)")


# =============================================================================
# Status Display Abstraction
# =============================================================================
# update_status(text) — single function, defined once per display type.
# TFT: shows text as-is. Seg display: extracts last number and shows it.
# No display: no-op. Call sites just pass a string.

def _extract_last_number(text):
    """Extract the last integer from a string. Returns None if not found."""
    num_str = ""
    found = None
    for c in text:
        if '0' <= c <= '9':
            num_str += c
        else:
            if num_str:
                found = int(num_str)
                num_str = ""
    if num_str:
        found = int(num_str)
    return found


if HAS_TFT and HAS_SEG_DISPLAY:
    # Both displays (shouldn't happen in practice, but handle it)
    def update_status(text):
        status_label.text = text
        n = _extract_last_number(text)
        if n is not None:
            _seg_display_number(n)
elif HAS_TFT:
    def update_status(text):
        status_label.text = text
elif HAS_SEG_DISPLAY:
    def update_status(text):
        n = _extract_last_number(text)
        if n is not None:
            _seg_display_number(n)
else:
    def update_status(text):
        pass


# =============================================================================
# LED & Display Helpers
# =============================================================================


def get_button_color(btn_config, keytime_index):
    """Get color for button at specific keytime state.
    
    Args:
        btn_config: Button configuration dict
        keytime_index: Current keytime position (1-indexed)
        
    Returns:
        RGB tuple for the color
    """
    return get_color(get_button_state_config(btn_config, keytime_index).get("color", "white"))


def set_button_state(switch_idx, on):
    """Update LED and display for a button (1-indexed).
    
    Now uses ButtonState objects and supports keytime colors.
    """
    idx = switch_idx - 1
    if idx < 0 or idx >= BUTTON_COUNT:
        return

    btn_state = button_states[idx]
    btn_config = buttons[idx] if idx < len(buttons) else {"color": "white"}
    
    # Get color for current keytime state
    color_rgb = get_button_color(btn_config, btn_state.get_keytime())
    off_mode = btn_config.get("off_mode", "dim")  # "dim" or "off"

    # Update LED
    led_idx = switch_to_led(switch_idx)
    if led_idx is not None:
        rgb = color_rgb if on else get_off_color(color_rgb, off_mode)
        base = led_idx * 3
        for j in range(3):
            if base + j < LED_COUNT:
                pixels[base + j] = rgb
        pixels.show()

    # Update display
    if HAS_TFT and idx < len(button_labels):
        color_hex = rgb_to_hex(color_rgb if on else get_off_color_for_display(color_rgb, off_mode))
        button_labels[idx].color = color_hex
        if idx < len(button_boxes):
            _, box_palette = button_boxes[idx]
            box_palette[1] = color_hex


def init_leds():
    """Initialize all LEDs to off/dim state."""
    for i in range(1, BUTTON_COUNT + 1):
        set_button_state(i, False)


def clamp_pc_value(value):
    """Clamp PC value to valid MIDI range (0-127)."""
    return max(0, min(127, value))


def flash_pc_button(button_idx, flash_ms=PC_FLASH_DURATION_MS):
    """Light LED briefly for PC button press feedback.

    Args:
        button_idx: 1-indexed button number (matches set_button_state convention)
        flash_ms: flash duration in milliseconds
    """
    set_button_state(button_idx, True)
    pc_flash_timers[button_idx - 1] = time.monotonic() + flash_ms / 1000.0


def update_select_group(active_btn_num, group):
    """Activate one select-mode button and deactivate its group siblings.

    Iterates all buttons; for each select-mode member matching `group`,
    sets state on iff it's the active button. LED follows via set_button_state,
    which respects each button's own off_mode.

    Writes only LED + button_states; never sends MIDI. Safe to call from RX
    paths without infinite-loop risk.

    Args:
        active_btn_num: 1-indexed button number to activate (others in group deactivate)
        group: select_group string identifier; empty string is a no-op
    """
    if not group:
        return
    for i, cfg in enumerate(buttons):
        if cfg.get("mode") == "select" and cfg.get("select_group") == group:
            on = (i + 1) == active_btn_num
            button_states[i].state = on
            set_button_state(i + 1, on)


def switch_page(n):
    """Switch the active page in RAM and re-render everything page-dependent.

    Device never writes config to disk; this only mutates RAM. Reset-on-entry:
    button/keytimes/encoder state rebuild from config defaults (latches/cycles
    are NOT preserved across switches). pc_values[] (patch memory) is NOT reset.
    """
    global active_page, buttons
    global CC_ENCODER, CC_ENCODER_PUSH, ENC_MIN, ENC_MAX, ENC_INITIAL
    global ENC_ENABLED, ENC_PUSH_ENABLED, ENC_PUSH_MODE, ENC_CHANNEL
    global ENC_PUSH_CHANNEL, ENC_PUSH_CC_ON, ENC_PUSH_CC_OFF, ENC_STEPS
    global enc_config, enc_push_config
    global exp_config, exp1_config, exp2_config, CC_EXP1, CC_EXP2, EXP1_CHANNEL, EXP2_CHANNEL
    global button_states, keytimes_states, encoder_value, encoder_slot

    config["active_page"] = _clamp_page(n)
    active_page = get_active_page(config)
    buttons = active_page.get("buttons", [])

    enc_config = active_page.get("encoder", {"enabled": True, "cc": 11, "label": "ENC", "min": 0, "max": 127, "initial": 64})
    enc_push_config = enc_config.get("push", {"enabled": True, "cc": 14, "label": "PUSH", "mode": "momentary"})
    CC_ENCODER = enc_config.get("cc", 11)
    CC_ENCODER_PUSH = enc_push_config.get("cc", 14)
    ENC_MIN = enc_config.get("min", 0)
    ENC_MAX = enc_config.get("max", 127)
    ENC_INITIAL = enc_config.get("initial", 64)
    ENC_ENABLED = enc_config.get("enabled", True) and HAS_ENCODER
    ENC_PUSH_ENABLED = enc_push_config.get("enabled", True) and HAS_ENCODER
    ENC_PUSH_MODE = enc_push_config.get("mode", "momentary")
    _page_channel = active_page.get("global_channel", config.get("global_channel", 0))
    if not isinstance(_page_channel, int) or _page_channel < 0 or _page_channel > 15:
        _page_channel = config.get("global_channel", 0)
    ENC_CHANNEL = enc_config.get("channel", _page_channel)
    ENC_PUSH_CHANNEL = enc_push_config.get("channel", _page_channel)
    ENC_PUSH_CC_ON = enc_push_config.get("cc_on", 127)
    ENC_PUSH_CC_OFF = enc_push_config.get("cc_off", 0)
    ENC_STEPS = enc_config.get("steps", None)

    exp_config = active_page.get("expression", {})
    exp1_config = exp_config.get("exp1", {"enabled": True, "cc": 12, "label": "EXP1", "min": 0, "max": 127, "polarity": "normal", "threshold": 2})
    exp2_config = exp_config.get("exp2", {"enabled": True, "cc": 13, "label": "EXP2", "min": 0, "max": 127, "polarity": "normal", "threshold": 2})
    CC_EXP1 = exp1_config.get("cc", 12)
    CC_EXP2 = exp2_config.get("cc", 13)
    EXP1_CHANNEL = exp1_config.get("channel", _page_channel)
    EXP2_CHANNEL = exp2_config.get("channel", _page_channel)

    button_states = []
    for i in range(BUTTON_COUNT):
        _btn_cfg = buttons[i] if i < len(buttons) else {}
        button_states.append(ButtonState(
            cc=_btn_cfg.get("cc", 0),
            mode=_btn_cfg.get("mode", "toggle"),
            keytimes=_btn_cfg.get("keytimes", 1),
        ))

    keytimes_states = [None] * BUTTON_COUNT
    for i in range(BUTTON_COUNT):
        _kt_cfg = buttons[i] if i < len(buttons) else {}
        if _kt_cfg.get("mode") == "keytimes":
            _kt_threshold = get_long_press_threshold_ms(config, _kt_cfg)
            keytimes_states[i] = KeytimesButtonState(
                _kt_threshold, len(_kt_cfg.get("short", [])), len(_kt_cfg.get("long", [])))

    for i in range(BUTTON_COUNT):
        pc_flash_timers[i] = 0.0
        hid_flash_timers[i] = 0.0
    encoder_value = ENC_INITIAL
    encoder_slot = -1

    if HAS_TFT:
        for i in range(BUTTON_COUNT):
            _btn_cfg = buttons[i] if i < len(buttons) else {"label": str(i + 1), "color": "white"}
            _color_rgb = get_color(_btn_cfg.get("color", "white"))
            _off_color = get_off_color_for_display(_color_rgb, _btn_cfg.get("off_mode", "dim"))
            button_labels[i].text = _btn_cfg.get("label", str(i + 1))[:6]
            button_labels[i].color = rgb_to_hex(_off_color)
            _, _box_palette = button_boxes[i]
            _box_palette[1] = rgb_to_hex(_off_color)
        if HAS_EXPRESSION and exp1_label is not None:
            exp1_label.text = exp1_config.get("label", "EXP1") + ": ---"
            exp2_label.text = exp2_config.get("label", "EXP2") + ": ---"

    init_leds()


def handle_pc_select_press(btn_num, btn_config, channel):
    """Handle a select-mode PC button activation (local press).

    Sends PC and claims active membership in the select group. Honors
    select_repress for already-active presses.

    PC + select_repress="deselect" is preserved at config level but no-oped
    in firmware (falls through to the resend path here) — gated on #47
    multi-message support landing. Existing configs won't need migration
    once it does.
    """
    btn_state = button_states[btn_num - 1]
    program = btn_config.get("program", 0)
    group = btn_config.get("select_group", "")
    repress = btn_config.get("select_repress", "resend")

    if btn_state.state and repress == "nothing":
        return  # already active, suppress repeat

    # Note: PC + active + repress=="deselect" reaches here too (intentional V1 no-op).
    midi_send(ProgramChange(program), channel=channel)
    print(f"[MIDI TX] Ch{channel+1} PC{program} (switch {btn_num}, select)")
    update_status(f"TX PC{program}")
    update_select_group(btn_num, group)


def handle_cc_select_press(btn_num, btn_config, channel):
    """Handle a select-mode CC button activation (local press).

    Sends CC (cc_on for activate, cc_off for self-deselect) and updates
    select-group LEDs. Honors select_repress for already-active presses.
    """
    btn_state = button_states[btn_num - 1]
    cc = btn_config.get("cc", 0)
    cc_on = btn_config.get("cc_on", 127)
    cc_off = btn_config.get("cc_off", 0)
    group = btn_config.get("select_group", "")
    repress = btn_config.get("select_repress", "resend")

    if btn_state.state and repress == "nothing":
        return

    if btn_state.state and repress == "deselect":
        # Self-toggle off: send cc_off, this button off, group has no active member.
        midi_send(ControlChange(cc, cc_off), channel=channel)
        print(f"[MIDI TX] Ch{channel+1} CC{cc}={cc_off} (switch {btn_num}, select deselect)")
        update_status(f"TX CC{cc}={cc_off}")
        btn_state.state = False
        set_button_state(btn_num, False)
        return

    midi_send(ControlChange(cc, cc_on), channel=channel)
    print(f"[MIDI TX] Ch{channel+1} CC{cc}={cc_on} (switch {btn_num}, select)")
    update_status(f"TX CC{cc}={cc_on}")
    update_select_group(btn_num, group)


def _expire_flash_timers(timers, now):
    """Turn off LEDs for a single flash-timer array whose expiry has passed."""
    for i in range(BUTTON_COUNT):
        if timers[i] > 0 and now >= timers[i]:
            timers[i] = 0.0
            set_button_state(i + 1, False)


def update_pc_flash_timers():
    """Turn off LEDs whose flash period has expired. Call each main loop."""
    now = time.monotonic()
    _expire_flash_timers(pc_flash_timers, now)
    _expire_flash_timers(hid_flash_timers, now)


# =============================================================================
# Polling Functions
# =============================================================================


def _process_midi_msg(msg, source="USB"):
    """Process a received MIDI message — update LED/button state."""
    if not msg:
        return

    msg_channel = getattr(msg, 'channel', 0) or 0

    if isinstance(msg, ControlChange):
        cc = msg.control
        val = msg.value
        print(f"[MIDI RX {source}] Ch{msg_channel+1} CC{cc}={val}")
        for i, btn_config in enumerate(buttons):
            if btn_config.get("type", "cc") == "cc" and btn_config.get("cc") == cc and btn_config.get("channel", 0) == msg_channel:
                # Select-mode: activate this button and deactivate group siblings
                # only when value matches cc_on. Other values are ignored to avoid
                # false activation. update_select_group is LED/state-only, so no
                # MIDI echo and no feedback risk. select_repress is intentionally
                # not consulted on RX — it applies only to local presses; RX is
                # idempotent LED-and-state-only.
                if btn_config.get("mode") == "select":
                    if val == btn_config.get("cc_on", 127):
                        update_select_group(i + 1, btn_config.get("select_group", ""))
                    update_status(f"RX CC{cc}={val}")
                    break
                new_state = button_states[i].on_midi_receive(val)
                set_button_state(i + 1, new_state)
                update_status(f"RX CC{cc}={val}")
                break

    elif isinstance(msg, NoteOn):
        note = msg.note
        vel = msg.velocity
        print(f"[MIDI RX {source}] Ch{msg_channel+1} NoteOn{note} vel{vel}")
        for i, btn_config in enumerate(buttons):
            if btn_config.get("type") == "note" and btn_config.get("note") == note and btn_config.get("channel", 0) == msg_channel:
                set_button_state(i + 1, vel > 0)
                update_status(f"RX Note{note}")
                break

    elif isinstance(msg, NoteOff):
        note = msg.note
        print(f"[MIDI RX {source}] Ch{msg_channel+1} NoteOff{note}")
        for i, btn_config in enumerate(buttons):
            if btn_config.get("type") == "note" and btn_config.get("note") == note and btn_config.get("channel", 0) == msg_channel:
                set_button_state(i + 1, False)
                update_status(f"RX NoteOff{note}")
                break

    elif isinstance(msg, ProgramChange):
        program = msg.patch
        print(f"[MIDI RX {source}] Ch{msg_channel+1} PC{program}")
        pc_values[msg_channel] = program
        update_status(f"RX PC{program}")
        # Select-mode: activate the matching select-mode PC button and dim its
        # group siblings. LED/state-only (no MIDI echo), so no feedback risk.
        # select_repress is intentionally not consulted on RX — it applies only
        # to local presses; RX is idempotent LED-and-state-only.
        for i, btn_config in enumerate(buttons):
            if (btn_config.get("type") == "pc" and btn_config.get("mode") == "select"
                    and btn_config.get("program") == program
                    and btn_config.get("channel", 0) == msg_channel):
                update_select_group(i + 1, btn_config.get("select_group", ""))
                break


def handle_midi():
    """Handle incoming MIDI messages and MIDI thru (4-route matrix)."""
    # --- USB MIDI in ---
    usb_msg = midi.receive()
    if usb_msg:
        _process_midi_msg(usb_msg, source="USB")
        # USB -> DIN (cross)
        if MIDI_THRU_USB_TO_DIN and midi_serial is not None:
            try:
                midi_serial.send(usb_msg)
            except Exception:
                pass
        # USB -> USB (loopback to host; opt-in)
        if MIDI_THRU_USB_TO_USB:
            try:
                midi.send(usb_msg)
            except Exception:
                pass

    # --- 5-pin DIN MIDI in ---
    if midi_serial is not None:
        din_msg = midi_serial.receive()
        if din_msg:
            _process_midi_msg(din_msg, source="DIN")
            # DIN -> USB (cross)
            if MIDI_THRU_DIN_TO_USB:
                try:
                    midi.send(din_msg)
                except Exception:
                    pass
            # DIN -> DIN (classic MIDI THRU pass-through)
            if MIDI_THRU_DIN_TO_DIN:
                try:
                    midi_serial.send(din_msg)
                except Exception:
                    pass


def _dispatch_keytimes_message(msg, default_channel, btn_num):
    """Send a single Message dict (from a keytimes-mode entry) to MIDI or HID.

    Routes by msg["type"]. Falls back to default_channel for the button when the
    message itself doesn't specify a channel. Used by handle_switches() via the
    callback passed to dispatch_keytimes_events().
    """
    channel = msg.get("channel", default_channel)
    mtype = msg.get("type", "cc")
    if mtype == "cc":
        cc = msg.get("cc", 0)
        val = msg.get("value", 0)
        midi_send(ControlChange(cc, val), channel=channel)
        print(f"[MIDI TX] Ch{channel+1} CC{cc}={val} (switch {btn_num}, keytimes)")
        update_status(f"TX CC{cc}={val}")
    elif mtype == "note":
        note = msg.get("note", 60)
        vel = msg.get("velocity", 127)
        if vel > 0:
            midi_send(NoteOn(note, vel), channel=channel)
            print(f"[MIDI TX] Ch{channel+1} NoteOn{note} vel{vel} (switch {btn_num}, keytimes)")
        else:
            midi_send(NoteOff(note, 0), channel=channel)
            print(f"[MIDI TX] Ch{channel+1} NoteOff{note} (switch {btn_num}, keytimes)")
        update_status(f"TX Note{note}")
    elif mtype == "pc":
        program = msg.get("program", 0)
        midi_send(ProgramChange(program), channel=channel)
        pc_values[channel] = program
        print(f"[MIDI TX] Ch{channel+1} PC{program} (switch {btn_num}, keytimes)")
        update_status(f"TX PC{program}")
    elif mtype in ("pc_inc", "pc_dec"):
        step = msg.get("step", 1)
        delta = step if mtype == "pc_inc" else -step
        pc_values[channel] = clamp_pc_value(pc_values[channel] + delta)
        midi_send(ProgramChange(pc_values[channel]), channel=channel)
        print(f"[MIDI TX] Ch{channel+1} PC{pc_values[channel]} (switch {btn_num}, keytimes {mtype})")
        update_status(f"TX PC{pc_values[channel]}")
    elif mtype == "hid":
        action = msg.get("action", "send")
        key = msg.get("key")
        modifier = msg.get("modifier")
        delay_ms = msg.get("delay_ms", 50)
        dispatch_hid(hid_keyboard, hid_mouse, action, key, modifier, delay_ms)
        key_label = key if key else "?"
        print(f"[HID TX] {action} {key_label} (switch {btn_num}, keytimes)")
        update_status(f"HID {action}")


def _render_keytimes_led(btn_num, state, btn_config):
    """Update LED + display for a mode: "keytimes" button based on its current state.

    LED uses full two-layer composition: long decorates short (the long cycle is a
    persistent modifier painted over the short cycle). Both layers are always passed
    to compute_keytimes_led_color() — short="off" is still a kill-switch that overrides
    long; long="off" is transparent (falls through to short).

    Label TEXT uses last_fired: only the most recently fired timing class supplies
    the label string. This prevents the stale-label bug (#143) where the first long
    press left its label stuck on every subsequent short press.

    Label COLOR is the composed color recomputed at full brightness (dim stripped),
    with a fallback to the button color so it is never black-on-black (#143).
    """
    idx = btn_num - 1
    if idx < 0 or idx >= BUTTON_COUNT:
        return

    # LED: full composition. long decorates short; last_fired doesn't gate this.
    rgb = compute_keytimes_led_color(state.short_color, state.short_dim,
                                     state.long_color, state.long_dim,
                                     btn_config.get("color"))

    led_idx = switch_to_led(btn_num)
    if led_idx is not None:
        base = led_idx * 3
        for j in range(3):
            if base + j < LED_COUNT:
                pixels[base + j] = rgb
        pixels.show()

    if HAS_TFT and idx < len(button_labels):
        # Label text: last_fired class owns the string. long falls back to short_label
        # then button label (a labelless long entry shows the prior short label);
        # short falls straight to the button label.
        if state.last_fired == "long":
            effective_label = (state.long_label or state.short_label or btn_config.get("label", ""))[:6]
        elif state.last_fired == "short":
            effective_label = (state.short_label or btn_config.get("label", ""))[:6]
        else:
            effective_label = btn_config.get("label", "")[:6]
        button_labels[idx].text = effective_label
        # Label color: composed color at full brightness so dim entries remain legible
        # (#143). black-on-black (kill-switch / no-color) falls back to button color.
        label_rgb = compute_keytimes_led_color(state.short_color, False,
                                               state.long_color, False,
                                               btn_config.get("color"))
        if not any(label_rgb):
            label_rgb = get_color(btn_config.get("color") or "white")
        button_labels[idx].color = rgb_to_hex(label_rgb)
        if idx < len(button_boxes):
            _, box_palette = button_boxes[idx]
            box_palette[1] = rgb_to_hex(rgb)


def handle_switches():
    """Handle footswitch presses with keytimes support."""
    # STD10: index 0 is encoder push, 1-10 are footswitches
    # Mini6: indices 0-5 are footswitches (no encoder)
    start_idx = 1 if HAS_ENCODER else 0
    now = time.monotonic()
    for i in range(start_idx, len(switches)):
        sw = switches[i]
        btn_num = i if HAS_ENCODER else i + 1
        idx = btn_num - 1
        btn_config = buttons[idx] if idx < len(buttons) else {"cc": 20 + idx}

        # Keytimes mode (#48): poll-driven dispatch via PressTracker. Runs every loop iteration
        # so the long-press threshold timer fires even when the switch state is steady.
        if btn_config.get("mode") == "keytimes":
            # Defensive: keytimes_states is sized to BUTTON_COUNT; idx should already be < BUTTON_COUNT
            # given the switches loop above, but guard explicitly to mirror the buttons[] fallback at L1084.
            if idx >= len(keytimes_states):
                continue
            kt_state = keytimes_states[idx]
            if kt_state is None:
                continue
            events = kt_state.tracker.update(sw.pressed, now)
            if events:
                default_channel = btn_config.get("channel", 0)
                dispatch_keytimes_events(
                    events, kt_state, btn_config,
                    lambda msg: _dispatch_keytimes_message(msg, default_channel, btn_num)
                )
                _render_keytimes_led(btn_num, kt_state, btn_config)
            continue

        # Legacy modes (toggle/momentary/flash/select): edge-triggered dispatch.
        changed, pressed = sw.changed()

        if changed:
            btn_state = button_states[idx]

            message_type = btn_config.get("type", "cc")
            mode = btn_config.get("mode", "toggle")
            channel = btn_config.get("channel", 0)

            if message_type == "cc":
                if mode == "select":
                    if pressed:
                        handle_cc_select_press(btn_num, btn_config, channel)
                    continue
                if pressed:
                    btn_state.advance_keytime()
                state_cfg = get_button_state_config(btn_config, btn_state.get_keytime())
                cc = state_cfg.get("cc", 20 + idx)
                cc_on = state_cfg.get("cc_on", 127)
                cc_off = state_cfg.get("cc_off", 0)
                if mode == "momentary":
                    val = cc_on if pressed else cc_off
                    set_button_state(btn_num, pressed)
                    midi_send(ControlChange(cc, val), channel=channel)
                    print(f"[MIDI TX] Ch{channel+1} CC{cc}={val} (switch {btn_num}, momentary)")
                    update_status(f"TX CC{cc}={val}")
                elif pressed:
                    # Keytimes cycling always stays on; standard toggle flips on/off
                    new_state = True if btn_state.keytimes > 1 else not btn_state.state
                    btn_state.state = new_state
                    set_button_state(btn_num, new_state)
                    val = cc_on if new_state else cc_off
                    midi_send(ControlChange(cc, val), channel=channel)
                    print(f"[MIDI TX] Ch{channel+1} CC{cc}={val} (switch {btn_num}, toggle)")
                    update_status(f"TX CC{cc}={val}")

            elif message_type == "note":
                if pressed:
                    btn_state.advance_keytime()
                state_cfg = get_button_state_config(btn_config, btn_state.get_keytime())
                note = state_cfg.get("note", 60)
                vel_on = state_cfg.get("velocity_on", 127)
                vel_off = state_cfg.get("velocity_off", 0)
                if mode == "momentary":
                    if pressed:
                        midi_send(NoteOn(note, vel_on), channel=channel)
                        set_button_state(btn_num, True)
                        print(f"[MIDI TX] Ch{channel+1} NoteOn{note} vel{vel_on} (switch {btn_num})")
                        update_status(f"TX Note{note}")
                    else:
                        midi_send(NoteOff(note, vel_off), channel=channel)
                        set_button_state(btn_num, False)
                        print(f"[MIDI TX] Ch{channel+1} NoteOff{note} (switch {btn_num})")
                elif pressed:
                    # Keytimes cycling always stays on; standard toggle flips on/off
                    new_state = True if btn_state.keytimes > 1 else not btn_state.state
                    btn_state.state = new_state
                    set_button_state(btn_num, new_state)
                    if new_state:
                        midi_send(NoteOn(note, vel_on), channel=channel)
                        print(f"[MIDI TX] Ch{channel+1} NoteOn{note} vel{vel_on} (switch {btn_num}, toggle on)")
                        update_status(f"TX Note{note} ON")
                    else:
                        midi_send(NoteOff(note, vel_off), channel=channel)
                        print(f"[MIDI TX] Ch{channel+1} NoteOff{note} (switch {btn_num}, toggle off)")
                        update_status(f"TX Note{note} OFF")

            elif message_type == "pc":
                if mode == "select":
                    if pressed:
                        handle_pc_select_press(btn_num, btn_config, channel)
                    continue
                if pressed:
                    btn_state.advance_keytime()
                    state_cfg = get_button_state_config(btn_config, btn_state.get_keytime())
                    program = state_cfg.get("program", 0)
                    midi_send(ProgramChange(program), channel=channel)
                    print(f"[MIDI TX] Ch{channel+1} PC{program} (switch {btn_num})")
                    update_status(f"TX PC{program}")
                    if mode == "toggle":
                        new_state = not btn_state.state
                        btn_state.state = new_state
                        set_button_state(btn_num, new_state)
                    elif mode == "momentary":
                        btn_state.state = True
                        set_button_state(btn_num, True)
                    else:  # "flash" (default)
                        flash_pc_button(btn_num, btn_config.get("flash_ms", PC_FLASH_DURATION_MS))
                elif mode == "momentary":
                    btn_state.state = False
                    set_button_state(btn_num, False)

            elif message_type == "pc_inc":
                if pressed:
                    btn_state.advance_keytime()
                    state_cfg = get_button_state_config(btn_config, btn_state.get_keytime())
                    step = state_cfg.get("pc_step", 1)
                    pc_values[channel] = clamp_pc_value(pc_values[channel] + step)
                    midi_send(ProgramChange(pc_values[channel]), channel=channel)
                    print(f"[MIDI TX] Ch{channel+1} PC{pc_values[channel]} (switch {btn_num}, inc)")
                    update_status(f"TX PC{pc_values[channel]}")
                    if mode == "toggle":
                        new_state = not btn_state.state
                        btn_state.state = new_state
                        set_button_state(btn_num, new_state)
                    elif mode == "momentary":
                        btn_state.state = True
                        set_button_state(btn_num, True)
                    else:  # "flash" (default)
                        flash_pc_button(btn_num, btn_config.get("flash_ms", PC_FLASH_DURATION_MS))
                elif mode == "momentary":
                    btn_state.state = False
                    set_button_state(btn_num, False)

            elif message_type == "pc_dec":
                if pressed:
                    btn_state.advance_keytime()
                    state_cfg = get_button_state_config(btn_config, btn_state.get_keytime())
                    step = state_cfg.get("pc_step", 1)
                    pc_values[channel] = clamp_pc_value(pc_values[channel] - step)
                    midi_send(ProgramChange(pc_values[channel]), channel=channel)
                    print(f"[MIDI TX] Ch{channel+1} PC{pc_values[channel]} (switch {btn_num}, dec)")
                    update_status(f"TX PC{pc_values[channel]}")
                    if mode == "toggle":
                        new_state = not btn_state.state
                        btn_state.state = new_state
                        set_button_state(btn_num, new_state)
                    elif mode == "momentary":
                        btn_state.state = True
                        set_button_state(btn_num, True)
                    else:  # "flash" (default)
                        flash_pc_button(btn_num, btn_config.get("flash_ms", PC_FLASH_DURATION_MS))
                elif mode == "momentary":
                    btn_state.state = False
                    set_button_state(btn_num, False)

            elif message_type == "hid" and pressed:
                btn_state.advance_keytime()
                state_cfg = get_button_state_config(btn_config, btn_state.get_keytime())
                # Resolve effective HID parameters from per-state override or base config.
                # Future: when multi-action-per-press is added, replace these four fields
                # with a hid_sequence list and iterate dispatch_hid() over each item.
                hid_action = state_cfg.get("hid_action") or btn_config.get("hid_action", "send")
                hid_key = state_cfg.get("hid_key") or btn_config.get("hid_key")
                hid_modifier = state_cfg.get("hid_modifier") or btn_config.get("hid_modifier")
                hid_delay_ms = state_cfg.get("hid_delay_ms") or btn_config.get("hid_delay_ms", 50)
                dispatch_hid(hid_keyboard, hid_mouse, hid_action, hid_key, hid_modifier, hid_delay_ms)
                key_label = hid_key if hid_key else "?"
                print(f"[HID TX] {hid_action} {key_label} (switch {btn_num})")
                update_status(f"HID {hid_action}")
                mode = btn_config.get("mode", "momentary")
                if mode == "toggle" and hid_action != "delay":
                    btn_state.state = not btn_state.state
                    set_button_state(btn_num, btn_state.state)
                elif hid_action != "delay":
                    # Flash LED briefly for press/send/release — delay doesn't need feedback
                    set_button_state(btn_num, True)
                    hid_flash_timers[btn_num - 1] = time.monotonic() + PC_FLASH_DURATION_MS / 1000.0


def handle_encoder_button():
    """Handle encoder push button."""
    global encoder_push_state
    
    if not ENC_PUSH_ENABLED:
        return
    
    sw = switches[0]  # Encoder push is switch index 0
    changed, pressed = sw.changed()
    if changed:
        if ENC_PUSH_MODE == "toggle":
            # Toggle mode: flip state on press only
            if pressed:
                encoder_push_state = not encoder_push_state
                cc_val = ENC_PUSH_CC_ON if encoder_push_state else ENC_PUSH_CC_OFF
                midi_send(ControlChange(CC_ENCODER_PUSH, cc_val), channel=ENC_PUSH_CHANNEL)
                print(f"[MIDI TX] Ch{ENC_PUSH_CHANNEL+1} CC{CC_ENCODER_PUSH}={cc_val} (encoder push, toggle)")
                update_status(f"TX CC{CC_ENCODER_PUSH}={cc_val}")
        else:
            # Momentary mode: send on press and release
            cc_val = ENC_PUSH_CC_ON if pressed else ENC_PUSH_CC_OFF
            midi_send(ControlChange(CC_ENCODER_PUSH, cc_val), channel=ENC_PUSH_CHANNEL)
            print(f"[MIDI TX] Ch{ENC_PUSH_CHANNEL+1} CC{CC_ENCODER_PUSH}={cc_val} (encoder push, momentary)")
            update_status(f"TX CC{CC_ENCODER_PUSH}={cc_val}")


def handle_encoder():
    """Handle rotary encoder."""
    global encoder_last_pos, encoder_value, encoder_slot
    
    if not ENC_ENABLED:
        return

    pos = encoder.position
    if pos != encoder_last_pos:
        delta = pos - encoder_last_pos
        encoder_last_pos = pos
        
        # Update internal value (always 0-127)
        encoder_value = max(0, min(127, encoder_value + delta))
        
        if ENC_STEPS and ENC_STEPS > 1:
            # Stepped mode: calculate which slot we're in
            # Slot boundaries: 0-25=slot0, 26-50=slot1, etc. for 5 slots
            slot_size = 128 // ENC_STEPS
            new_slot = min(encoder_value // slot_size, ENC_STEPS - 1)
            
            if new_slot != encoder_slot:
                encoder_slot = new_slot
                # Output CC is the slot number (0 to steps-1)
                midi_send(ControlChange(CC_ENCODER, encoder_slot), channel=ENC_CHANNEL)
                print(f"[ENCODER] Ch{ENC_CHANNEL+1} CC{CC_ENCODER}={encoder_slot} (slot)")
                update_status(f"ENC slot {encoder_slot}")
        else:
            # Normal mode: send every change
            midi_send(ControlChange(CC_ENCODER, encoder_value), channel=ENC_CHANNEL)
            print(f"[ENCODER] Ch{ENC_CHANNEL+1} CC{CC_ENCODER}={encoder_value}")
            update_status(f"ENC={encoder_value}")


def handle_expression():
    """Handle expression pedals."""
    global exp1_min, exp1_max, exp1_last
    global exp2_min, exp2_max, exp2_last

    if not HAS_EXPRESSION:
        return

    # Expression 1
    if exp1_config.get("enabled", True) and exp1 is not None:
        raw1 = exp1.value
        exp1_max = max(raw1, exp1_max)
        exp1_min = min(raw1, exp1_min)
        
        if exp1_max > exp1_min:
            # Map to 0-127, then apply config range
            normalized = (raw1 - exp1_min) / (exp1_max - exp1_min)
            if exp1_config.get("polarity", "normal") == "reverse":
                normalized = 1.0 - normalized
            out_min = exp1_config.get("min", 0)
            out_max = exp1_config.get("max", 127)
            val1 = int(out_min + normalized * (out_max - out_min))
            val1 = max(0, min(127, val1))  # Clamp to valid MIDI range
            
            # Hysteresis: only send if change exceeds threshold
            threshold = exp1_config.get("threshold", 2)
            if abs(val1 - exp1_last) >= threshold:
                exp1_last = val1
                midi_send(ControlChange(CC_EXP1, val1), channel=EXP1_CHANNEL)
                lbl = exp1_config.get("label", "EXP1")
                print(f"[{lbl}] Ch{EXP1_CHANNEL+1} CC{CC_EXP1}={val1}")
                # Update display
                if exp1_label:
                    exp1_label.text = f"{lbl}: {val1:3d}"

    # Expression 2
    if exp2_config.get("enabled", True) and exp2 is not None:
        raw2 = exp2.value
        exp2_max = max(raw2, exp2_max)
        exp2_min = min(raw2, exp2_min)
        
        if exp2_max > exp2_min:
            # Map to 0-127, then apply config range
            normalized = (raw2 - exp2_min) / (exp2_max - exp2_min)
            if exp2_config.get("polarity", "normal") == "reverse":
                normalized = 1.0 - normalized
            out_min = exp2_config.get("min", 0)
            out_max = exp2_config.get("max", 127)
            val2 = int(out_min + normalized * (out_max - out_min))
            val2 = max(0, min(127, val2))  # Clamp to valid MIDI range
            
            # Hysteresis: only send if change exceeds threshold
            threshold = exp2_config.get("threshold", 2)
            if abs(val2 - exp2_last) >= threshold:
                exp2_last = val2
                midi_send(ControlChange(CC_EXP2, val2), channel=EXP2_CHANNEL)
                lbl = exp2_config.get("label", "EXP2")
                print(f"[{lbl}] Ch{EXP2_CHANNEL+1} CC{CC_EXP2}={val2}")
                # Update display
                if exp2_label:
                    exp2_label.text = f"{lbl}: {val2:3d}"


# =============================================================================
# Startup
# =============================================================================

def _clamp_page(n):
    pages = config.get("pages", [])
    if not pages:
        return 0
    if not isinstance(n, int) or isinstance(n, bool):
        return 0
    return max(0, min(n, len(pages) - 1))


print("Initializing...")
switch_page(_clamp_page(config.get("active_page", 0)))

# Startup animation
pixels.fill((0, 255, 0))
pixels.show()
if HAS_SEG_DISPLAY:
    _seg_boot_animation()
else:
    time.sleep(0.5)
init_leds()

# Show CC mapping info
if HAS_ENCODER:
    if ENC_STEPS and ENC_STEPS > 1:
        print(f"Encoder: Ch{ENC_CHANNEL+1} CC{CC_ENCODER} ({ENC_STEPS} slots, outputs 0-{ENC_STEPS-1})")
    else:
        print(f"Encoder: Ch{ENC_CHANNEL+1} CC{CC_ENCODER} (range {ENC_MIN}-{ENC_MAX}, init={ENC_INITIAL})")
    print(f"Encoder Push: Ch{ENC_PUSH_CHANNEL+1} CC{CC_ENCODER_PUSH} ({ENC_PUSH_MODE})")
if HAS_EXPRESSION:
    print(f"Expression 1: Ch{EXP1_CHANNEL+1} CC{CC_EXP1}")
    print(f"Expression 2: Ch{EXP2_CHANNEL+1} CC{CC_EXP2}")
for i, btn in enumerate(buttons):
    btn_channel = btn.get("channel", 0)
    print(f"Button {i+1}: Ch{btn_channel+1} CC{btn.get('cc', 20+i)} ({btn.get('label', '')})")

print("\nRunning...")

# Mark this boot as having reached steady state. boot.py reads this NVM
# byte on next power-up; if still 1, the previous boot didn't complete
# and boot.py runs a compile-check to diagnose a SyntaxError brick.
import microcontroller
microcontroller.nvm[0] = 0

# RAM watch (dev_mode only): report free heap after full init, then track the
# reclaimable low-water mark over the session. Useful as the Pages feature (#15)
# grows per-config memory -- compare against pages_ram_probe.py `retained` to see
# how much page headroom remains on real hardware. Performance mode skips it
# entirely (single bool test per loop), so there's no live-playing cost.
import gc

DEV_MODE = get_dev_mode(config)
_ram_low = None
_ram_next_check = 0.0
RAM_CHECK_INTERVAL_S = 2.0

if DEV_MODE:
    gc.collect()
    _ram_low = gc.mem_free()
    print("free after boot:", _ram_low, "bytes")

# =============================================================================
# Main Loop
# =============================================================================

while True:
    handle_midi()
    handle_switches()
    update_pc_flash_timers()
    if HAS_ENCODER:
        handle_encoder_button()
        handle_encoder()
    if HAS_EXPRESSION:
        handle_expression()
    if DEV_MODE:
        # Throttled reclaimable-RAM sample. gc.collect() first so the reading
        # reflects true free heap (not transient uncollected garbage); only
        # every RAM_CHECK_INTERVAL_S to keep the collect off the hot path.
        _now = time.monotonic()
        if _now >= _ram_next_check:
            _ram_next_check = _now + RAM_CHECK_INTERVAL_S
            gc.collect()
            _free = gc.mem_free()
            if _free < _ram_low:
                _ram_low = _free
                print("ram low-water:", _free, "bytes")
