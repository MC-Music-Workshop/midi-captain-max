# Tests Agent Instructions

Run everything from the repo root with `./tools/test-all.sh`, or just Python with `python3 -m pytest tests/`.

## Layers

| Layer | What it runs | Where | Cost |
|---|---|---|---|
| Unit tests | Pure modules (`core/*.py`), the config validator, the schema | `tests/test_*.py` | Free, every run |
| **Firmware harness** | The real `firmware/dev/code.py` on desktop mocks: boot, press switches, read MIDI / LEDs / serial | `tests/firmware_harness.py`, `boot` fixture in `tests/conftest.py` | Free, every run |
| **Wokwi scenario replay** | Each `emulator/scenarios/*/scenario.yaml` replayed on the firmware harness | `tests/test_wokwi_scenarios.py` | Free, every push (CI's pytest step) |
| Wokwi emulator | The same scenarios on real CircuitPython 7.3.3 in Wokwi's simulated Pico | `./emulator/run-scenario.sh` locally; `.github/workflows/wokwi.yml` on PRs (see [`emulator/README.md`](../emulator/README.md)) | Wokwi cloud minutes: PR opened/ready, `wokwi` label, or manual |
| Bench | A real pedal | `tools/bench/run.sh`, [`docs/bench-tests.md`](../docs/bench-tests.md) | A pedal |

Use the cheapest layer that can see the behavior. Anything in `handle_switches()`, `_process_midi_msg()`, page switching or the button dispatch path belongs in the firmware harness; reach for Wokwi to confirm it on real CircuitPython, and the bench for LEDs, the display and real MIDI.

## Firmware harness (`tests/firmware_harness.py`)

`boot(cfg)` (fixture) execs `code.py` up to, not including, its `while True:` main loop with your config as `/config.json`, and returns a `Pedal`. Only the hardware is fake: `adafruit_midi` records sends, display and font libraries are `MagicMock`, `time.monotonic` is a manual clock, and the `tests/mocks/` modules stand in for `board`, `digitalio`, `neopixel` and friends.

How:

```python
from tests.firmware_harness import cc, ProgramChange

def test_footswitch_1_toggles(boot):
    pedal = boot({"device": "std10", "pages": [{"buttons": [...10 buttons...]}]})
    pedal.tap(1)                          # switch index: STD10 0 = encoder push, 1-10 = footswitches
    assert pedal.sent() == [cc(20, 127)]  # USB MIDI since the last sent(), as (msg, channel)
    assert pedal["button_states"][0].state
```

`Pedal` API:

- `press(i)`, `release(i)`, `tap(i)`, `set(i, pressed)`: change a switch and run one loop pass (`handle_switches`, `flush_cc_step_updates`, `update_pc_flash_timers`).
- `advance(seconds)`: move the clock and run a loop pass (long-press thresholds, flash expiry). `hold(i, seconds)` is press + advance + release.
- `receive(msg)`: process an incoming MIDI message, e.g. `pedal.receive(ControlChange(70, 127, channel=0))`.
- `sent()`: USB MIDI sent since the last call, then clears. `leds()`: NeoPixel colors. `serial()`: everything `code.py` printed, boot banner included.
- `pedal["name"]`: any `code.py` global (`buttons`, `button_states`, `config`, `switch_page`, ...). Assigning `pedal.ns["dispatch_hid"] = fake` swaps a function, since `code.py` looks globals up at call time.

Gotchas:

- Switch indexes follow `SWITCH_PINS` for the device. On STD10, index 0 is the encoder push, which `code.py` treats as logical button 11 (`buttons[10]`, `button_states[10]`).
- The clock starts at 1000 s and only moves when you call `advance`/`hold`. A keytimes short entry's `down` fires on press; the long entry's `down` fires only after `advance` past the threshold (default 500 ms) while held.
- Each `boot()` gets fresh `code.py` globals, but `core.*` modules are imported once per pytest process. They're stateless, so this hasn't mattered.
- `tests/test_code_encoder_push.py` is the worked example, including a smoke test that boots every shipped `firmware/dev/config*.json` and taps and holds every switch.

## Wokwi scenario replay (`tests/test_wokwi_scenarios.py`)

Every `emulator/scenarios/<name>/` (a `config.json` + `scenario.yaml`) is replayed on the harness, mapping each Wokwi part to a switch through `emulator/diagram.json` and `SWITCH_PINS`. It follows Wokwi's timing rule (a `wait-serial` only sees text printed after the step starts), so a scenario that would hang on Wokwi fails here first, for free. Write and debug a scenario against this test, then spend Wokwi minutes once it passes.

Needs PyYAML (`requirements-dev.txt`). A new scenario directory is picked up automatically by both the replay and the Wokwi workflow.

## Fixtures

`tests/fixtures/editor-saved-encoder-push.json` is the exact JSON the config editor's Save to File… wrote. Rust (`config_files.rs`) saves it through the real `write_config_file`, and `test_code_encoder_push.py` boots it, so editor → Rust → firmware stay in agreement. Regenerate it from the editor if the save format changes on purpose.
