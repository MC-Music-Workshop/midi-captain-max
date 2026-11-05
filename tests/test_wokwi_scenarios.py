"""
Replays every Wokwi scenario (emulator/scenarios/<name>/scenario.yaml + config.json) on
the desktop harness (tests/firmware_harness.py), so a scenario is checked for free on
every test run before it spends Wokwi cloud minutes in ./emulator/run-scenario.sh.

Supported steps (the subset the scenarios use): `set-control` with control `pressed`
on a pushbutton wired in emulator/diagram.json, `delay` (ms/s), and `wait-serial`.

Mirrors Wokwi's timing rule, which a scenario must respect: `wait-serial` only sees
text printed AFTER the step starts. Here, set-control runs the firmware instantly, so
its output counts for the waits that follow it; anything printed before or during a
`delay` is gone. A wait advances the clock (10 ms loop passes, up to 10 s) until its
line appears, which is how a long press fires while a scenario waits for it.
So write `press -> wait-serial -> release -> wait-serial`, never a wait after a delay.
"""

import json
from pathlib import Path

import pytest
import yaml

EMULATOR = Path(__file__).resolve().parent.parent / "emulator"
SCENARIOS = sorted(p for p in (EMULATOR / "scenarios").glob("*") if (p / "scenario.yaml").exists())


def _part_pins():
    """{part-id: "GPn"} for every pushbutton wired to a Pico GPIO in diagram.json."""
    diagram = json.loads((EMULATOR / "diagram.json").read_text())
    pins = {}
    for a, b, *_ in diagram["connections"]:
        for pico_end, part_end in ((a, b), (b, a)):
            if pico_end.startswith("pico:GP"):
                pins[part_end.split(":")[0]] = pico_end.split(":")[1]
    return pins


def _seconds(delay):
    delay = str(delay).strip()
    return float(delay[:-2]) / 1000 if delay.endswith("ms") else float(delay.rstrip("s"))


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda p: p.name)
def test_scenario_replays_on_desktop(boot, scenario):
    pedal = boot(json.loads((scenario / "config.json").read_text()))
    pin_to_switch = {pin.name: i for i, pin in enumerate(pedal["SWITCH_PINS"])}
    part_to_switch = {part: pin_to_switch[pin] for part, pin in _part_pins().items() if pin in pin_to_switch}
    cursor = 0  # waits only match output after this point (see module docstring)
    for n, step in enumerate(yaml.safe_load((scenario / "scenario.yaml").read_text())["steps"], 1):
        if "set-control" in step:
            ctl = step["set-control"]
            assert ctl["control"] == "pressed", f"step {n}: only 'pressed' is replayed"
            pedal.set(part_to_switch[ctl["part-id"]], bool(ctl["value"]))
        elif "delay" in step:
            pedal.advance(_seconds(step["delay"]))
            cursor = len(pedal.serial())
        elif "wait-serial" in step:
            text = step["wait-serial"]
            for _ in range(1000):
                at = pedal.serial().find(text, cursor)
                if at >= 0:
                    break
                pedal.advance(0.01)
            assert at >= 0, (f"step {n}: never printed {text!r} (or printed it before this wait began)"
                             f"\n--- serial since the last wait/delay ---\n{pedal.serial()[cursor:]}")
            cursor = at + len(text)
        else:
            pytest.fail(f"step {n}: unsupported step {step}")
