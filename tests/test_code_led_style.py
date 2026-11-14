"""
LedStyle (per-LED colors, flash and spin animations) on the real firmware/dev/code.py,
booted on desktop mocks by the `boot` fixture (tests/firmware_harness.py).

STD10: switch index 1 is footswitch 1, whose three LEDs are pixels 0..2.
"""

import json

from tests.firmware_harness import FW, ControlChange
from core.colors import COLORS, dim_color

R, G, B, W, OFF = COLORS["red"], COLORS["green"], COLORS["blue"], COLORS["white"], COLORS["off"]
DARK = [OFF, OFF, OFF]


def std10(btn0):
    btns = [{"label": str(i + 1), "cc": 20 + i, "color": "white"} for i in range(10)]
    btns[0] = btn0
    return {"device": "std10", "pages": [{"buttons": btns}]}


def sw1(pedal):
    return pedal.leds()[0:3]


def test_led_on_pixels_and_dimmed_off(boot):
    pedal = boot(std10({"label": "RWG", "cc": 20, "color": "white",
                        "led_on": {"pixels": ["red", "white", "green"]}}))
    assert sw1(pedal) == [dim_color(R), dim_color(W), dim_color(G)]
    pedal.tap(1)
    assert sw1(pedal) == [R, W, G]
    assert pedal.leds()[3:6] == [dim_color(W)] * 3  # other switches untouched
    pedal.tap(1)
    assert sw1(pedal) == [dim_color(R), dim_color(W), dim_color(G)]


def test_flash_animation_runs_and_stops(boot):
    pedal = boot(std10({"label": "F", "cc": 20, "color": "red",
                        "led_on": {"animation": "flash", "speed_ms": 200}}))
    pedal.tap(1)
    assert sw1(pedal) == [R, R, R]
    pedal.advance(0.2)
    assert sw1(pedal) == DARK
    pedal.advance(0.2)
    assert sw1(pedal) == [R, R, R]
    pedal.tap(1)  # off: solid dim, animation stopped
    pedal.advance(0.2)
    assert sw1(pedal) == [dim_color(R)] * 3
    assert pedal["led_anims"][0] is None


def test_spin_animation(boot):
    pedal = boot(std10({"label": "S", "cc": 20, "color": "blue", "off_mode": "off",
                        "led_on": {"animation": "spin", "speed_ms": 100}}))
    pedal.tap(1)
    assert sw1(pedal) == [B, OFF, OFF]
    pedal.advance(0.1)
    assert sw1(pedal) == [OFF, B, OFF]
    pedal.advance(0.1)
    assert sw1(pedal) == [OFF, OFF, B]
    pedal.advance(0.1)
    assert sw1(pedal) == [B, OFF, OFF]


def test_led_off_style_animates_at_boot(boot):
    pedal = boot(std10({"label": "O", "cc": 20, "color": "white",
                        "led_off": {"pixels": ["green", "off", "green"], "animation": "flash", "speed_ms": 500}}))
    assert sw1(pedal) == [G, OFF, G]
    pedal.advance(0.5)
    assert sw1(pedal) == DARK


def test_host_resending_same_state_keeps_flash_phase(boot):
    # A chatty host repeats "on" constantly; the flash must keep blinking, not
    # restart (and stick in its on phase) on every message.
    pedal = boot(std10({"label": "H", "cc": 20, "color": "red",
                        "led_on": {"animation": "flash", "speed_ms": 200}}))
    pedal.receive(ControlChange(20, 127, channel=0))
    pedal.advance(0.1)
    pedal.receive(ControlChange(20, 127, channel=0))
    pedal.advance(0.1)
    assert sw1(pedal) == DARK


def test_pc_flash_mode_uses_led_on(boot):
    pedal = boot(std10({"label": "PC", "type": "pc", "program": 3, "color": "white", "off_mode": "off",
                        "led_on": {"pixels": ["red", "white", "green"]}}))
    pedal.tap(1)
    assert sw1(pedal) == [R, W, G]
    pedal.advance(0.3)  # default flash_ms 200
    assert sw1(pedal) == DARK


def keytimes_btn(**extra):
    btn = {"label": "K", "color": "white", "mode": "keytimes",
           "short": [
               {"down": [{"type": "cc", "cc": 30, "value": 127}],
                "led": {"pixels": ["red", "white", "green"], "animation": "spin", "speed_ms": 100}},
               {"down": [{"type": "cc", "cc": 30, "value": 0}], "color": "blue"},
           ]}
    btn.update(extra)
    return btn


def test_keytimes_entry_led(boot):
    pedal = boot(std10(keytimes_btn()))
    pedal.tap(1)
    assert sw1(pedal) == [R, W, G]
    pedal.advance(0.1)
    assert sw1(pedal) == [G, R, W]
    pedal.tap(1)  # second entry: plain solid blue
    assert sw1(pedal) == [B, B, B]
    pedal.advance(0.1)
    assert sw1(pedal) == [B, B, B]


def test_keytimes_entry_led_from_host(boot):
    btn = keytimes_btn(short_cc_receive=40)
    btn["short"][0]["rx_value"] = 1
    btn["short"][1]["rx_value"] = 2
    pedal = boot(std10(btn))
    pedal.receive(ControlChange(40, 1, channel=0))
    assert sw1(pedal) == [R, W, G]
    pedal.advance(0.1)
    assert sw1(pedal) == [G, R, W]
    pedal.receive(ControlChange(40, 2, channel=0))
    assert sw1(pedal) == [B, B, B]


def test_page_switch_stops_animation(boot):
    cfg = std10({"label": "F", "cc": 20, "color": "red",
                 "led_on": {"animation": "flash", "speed_ms": 200}})
    cfg["pages"].append({"buttons": [{"label": str(i + 1), "cc": 50 + i, "color": "white"} for i in range(10)]})
    pedal = boot(cfg)
    pedal.tap(1)
    assert pedal["led_anims"][0] is not None
    pedal["switch_page"](1)
    pedal.advance(0.2)
    assert pedal["led_anims"][0] is None
    assert sw1(pedal) == [dim_color(W)] * 3


def test_shipped_configs_without_styles_never_animate(boot):
    # Configs without LED styles behave as before: nothing animates.
    for path in sorted(FW.glob("config*.json")):
        if path.name == "config-example-led-styles.json":
            continue
        pedal = boot(json.loads(path.read_text()))
        assert all(a is None for a in pedal["led_anims"]), path.name


def test_led_styles_example_config(boot):
    pedal = boot(json.loads((FW / "config-example-led-styles.json").read_text()))
    leds = pedal.leds()
    assert leds[12:15] == [COLORS["orange"], OFF, COLORS["orange"]]  # ARM: led_off flashes from boot
    pedal.tap(1)
    assert pedal.leds()[0:3] == [R, W, G]
    pedal.receive(ControlChange(60, 1, channel=0))  # host: LOOP is recording
    assert pedal.leds()[15:18] == [R, R, R]
    pedal.advance(0.25)
    assert pedal.leds()[15:18] == DARK
