"""
Per-LED colors and animations (LedStyle): the pure core/led_style.py module and
validate_led_style() in core/config.py. Firmware behavior on the real code.py is
in tests/test_code_led_style.py.
"""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.colors import COLORS, dim_color
from core.config import validate_button, validate_led_style
from core.led_style import (
    frame_index,
    resolve_button_led,
    resolve_keytimes_led,
    style_frames,
)

R, G, B, W, OFF = COLORS["red"], COLORS["green"], COLORS["blue"], COLORS["white"], COLORS["off"]
RWG = (R, W, G)


# --- style_frames / frame_index --------------------------------------------------

def test_solid_is_one_frame():
    assert style_frames(RWG, "solid") == (RWG,)


def test_flash_alternates_pattern_and_dark():
    assert style_frames(RWG, "flash") == (RWG, (OFF, OFF, OFF))


def test_spin_rotates_pattern():
    assert style_frames(RWG, "spin") == (RWG, (G, R, W), (W, G, R))


def test_spin_uniform_pattern_chases_one_led():
    assert style_frames((B, B, B), "spin") == ((B, OFF, OFF), (OFF, B, OFF), (OFF, OFF, B))


def test_dark_pattern_never_animates():
    assert style_frames((OFF, OFF, OFF), "flash") == ((OFF, OFF, OFF),)
    assert style_frames((OFF, OFF, OFF), "spin") == ((OFF, OFF, OFF),)


def test_frame_index_steps_every_speed_ms():
    assert frame_index(10.0, 10.0, 250, 3) == 0
    assert frame_index(10.0, 10.249, 250, 3) == 0
    assert frame_index(10.0, 10.25, 250, 3) == 1
    assert frame_index(10.0, 10.75, 250, 3) == 0  # wraps
    assert frame_index(10.0, 99.0, 250, 1) == 0


# --- resolve_button_led ------------------------------------------------------------

def test_no_style_on_off_matches_legacy():
    btn = {"color": "red", "off_mode": "dim"}
    assert resolve_button_led(btn, True, R) == ((R, R, R), "solid", 250)
    d = dim_color(R)
    assert resolve_button_led(btn, False, R)[0] == (d, d, d)


def test_led_on_pixels():
    btn = {"color": "white", "led_on": {"pixels": ["red", "white", "green"]}}
    assert resolve_button_led(btn, True, W)[0] == RWG


def test_led_on_animation_without_pixels_uses_color():
    btn = {"color": "blue", "led_on": {"animation": "flash", "speed_ms": 100}}
    assert resolve_button_led(btn, True, B) == ((B, B, B), "flash", 100)


def test_off_state_dims_led_on_pixels():
    btn = {"color": "white", "off_mode": "dim", "led_on": {"pixels": ["red", "off", "green"]}}
    assert resolve_button_led(btn, False, W)[0] == (dim_color(R), OFF, dim_color(G))


def test_off_state_extinguished_ignores_led_on_pixels():
    btn = {"color": "white", "off_mode": "off", "led_on": {"pixels": ["red", "off", "green"]}}
    assert resolve_button_led(btn, False, W)[0] == (OFF, OFF, OFF)


def test_off_color_beats_led_on_pixels():
    btn = {"color": "white", "off_color": "blue", "led_on": {"pixels": ["red", "off", "green"]}}
    assert resolve_button_led(btn, False, W)[0] == (B, B, B)


def test_led_off_pixels_beat_off_color_full_brightness():
    btn = {"color": "white", "off_color": "blue", "off_mode": "dim",
           "led_off": {"pixels": ["green", "green", "off"], "animation": "spin", "speed_ms": 80}}
    assert resolve_button_led(btn, False, W) == ((G, G, OFF), "spin", 80)


def test_led_on_animation_does_not_leak_into_off():
    btn = {"color": "red", "led_on": {"animation": "flash"}}
    assert resolve_button_led(btn, False, R)[1] == "solid"


# --- resolve_keytimes_led ----------------------------------------------------------

def kt(last_fired=None, sc=None, sd=False, sl=None, lc=None, ld=False, ll=None, color="white", overlay=False):
    return resolve_keytimes_led(last_fired, sc, sd, sl, lc, ld, ll, color, overlay)


def test_keytimes_entry_pixels_win_without_color():
    assert kt("short", sl={"pixels": ["red", "white", "green"]}) == (RWG, "solid", 250)


def test_keytimes_entry_animation_on_entry_color():
    assert kt("short", sc="red", sl={"animation": "flash", "speed_ms": 400}) == ((R, R, R), "flash", 400)


def test_keytimes_entry_animation_on_button_color_fallback():
    assert kt("short", sl={"animation": "spin"}, color="blue") == ((B, B, B), "spin", 250)


def test_keytimes_dim_applies_to_pixels():
    pattern = kt("short", sd=True, sl={"pixels": ["red", "off", "green"]})[0]
    assert pattern == (dim_color(R), OFF, dim_color(G))


def test_keytimes_short_off_kills_led_style():
    assert kt("short", sc="off", sl={"pixels": ["red", "red", "red"], "animation": "flash"}) == (
        (OFF, OFF, OFF), "solid", 250)


def test_keytimes_last_fired_gates_inactive_layer():
    # Long layer has pixels but short fired last: the short entry owns the LED.
    assert kt("short", sc="green", ll={"pixels": ["red", "red", "red"]})[0] == (G, G, G)
    assert kt("long", sc="green", ll={"pixels": ["red", "white", "green"]})[0] == RWG


def test_keytimes_long_overlay_long_pixels_decorate_short():
    assert kt("short", sc="green", ll={"pixels": ["red", "white", "green"]}, overlay=True)[0] == RWG


# --- validate_led_style / validate_button --------------------------------------------

def test_validate_led_style_full():
    assert validate_led_style({"pixels": ["Red", "white", "OFF"], "animation": "spin", "speed_ms": 120}) == {
        "pixels": ["red", "white", "off"], "animation": "spin", "speed_ms": 120}


def test_validate_led_style_clamps_and_defaults_speed():
    assert validate_led_style({"animation": "flash", "speed_ms": 1})["speed_ms"] == 50
    assert validate_led_style({"animation": "flash", "speed_ms": 99999})["speed_ms"] == 5000
    assert validate_led_style({"animation": "flash"})["speed_ms"] == 250
    assert validate_led_style({"animation": "flash", "speed_ms": True})["speed_ms"] == 250


def test_validate_led_style_drops_bad_parts():
    assert validate_led_style({"pixels": ["red", "white"]}) is None
    assert validate_led_style({"pixels": ["red", "white", "pink"]}) is None
    assert validate_led_style({"animation": "wobble", "pixels": ["red", "red", "red"]}) == {
        "pixels": ["red", "red", "red"]}
    # speed_ms means nothing on a solid style
    assert validate_led_style({"animation": "solid", "speed_ms": 100}) is None
    assert validate_led_style({}) is None
    assert validate_led_style("red") is None


def test_validate_button_keeps_led_styles():
    out = validate_button({"label": "A", "color": "white",
                           "led_on": {"pixels": ["red", "white", "green"]},
                           "led_off": {"animation": "flash"}})
    assert out["led_on"] == {"pixels": ["red", "white", "green"]}
    assert out["led_off"] == {"animation": "flash", "speed_ms": 250}


def test_validate_button_drops_led_styles_on_slot_buttons():
    out = validate_button({"label": "A", "color": "white", "type": "cc_inc", "cc_slots": 4,
                           "led_on": {"animation": "flash"}})
    assert "led_on" not in out


def test_validate_button_keeps_led_styles_on_step_buttons():
    out = validate_button({"label": "A", "color": "white", "type": "cc_inc",
                           "led_on": {"animation": "spin"}})
    assert out["led_on"]["animation"] == "spin"


def test_validate_keytimes_entry_led():
    out = validate_button({"label": "A", "color": "white", "mode": "keytimes",
                           "short": [{"down": [{"type": "cc", "cc": 1, "value": 127}],
                                      "led": {"pixels": ["red", "white", "green"], "animation": "flash"}}],
                           "led_on": {"animation": "flash"}})
    assert out["short"][0]["led"] == {"pixels": ["red", "white", "green"], "animation": "flash", "speed_ms": 250}
    assert "led_on" not in out  # keytimes buttons: entries own the LED
