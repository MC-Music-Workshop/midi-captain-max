# Emulator Testing (Wokwi)

Headless firmware testing using **Wokwi CLI** — runs actual CircuitPython 7.3.3 on a simulated RP2040.

## How it works

`wokwi-cli` uploads a UF2 to Wokwi's cloud simulator and streams serial output back. The key challenge: the CLI does **not** inject project files into CircuitPython's flash filesystem (that's a browser-only feature). The solution is an **all-in-one UF2** that bundles the CP runtime + a FAT12 filesystem containing our firmware.

`build-uf2.py` creates this bundle:
1. Formats a 1MB FAT12 image using `pyfatfs` (pure Python, cross-platform)
2. Populates it with `code.py`, `boot.py`, `config.json`, `core/`, `devices/`, `lib/`, `fonts/`
3. Converts the FAT image to UF2 blocks at flash offset `0x10100000`
4. Concatenates with the CircuitPython 7.3.3 firmware UF2

## Usage

```bash
pip install pyfatfs                         # one-time
./emulator/setup.sh                         # downloads CP UF2, builds firmware-bundle.uf2
export WOKWI_CLI_TOKEN=your_token           # from https://wokwi.com/dashboard/ci
./emulator/test.sh                          # automated: --expect-text "MIDI CAPTAIN" --fail-text "Traceback"
./emulator/run.sh                           # interactive
./emulator/run-scenario.sh emulator/scenarios/encoder-push   # press buttons, check serial (see Scenarios)
```

## Scenarios

A scenario presses buttons on the simulated pedal and checks the lines `code.py` prints. Every MIDI send prints one, e.g. `[MIDI TX] Ch1 CC14=127 (switch 11, momentary)`, and page switches print `[PAGE] page_inc -> page 1 (switch 10)`. Each scenario is a directory:

```
emulator/scenarios/<name>/
├── config.json     # baked into the simulated drive as /config.json
├── scenario.yaml   # Wokwi automation steps
└── serial.log      # written by each run — gitignored
```

How to run one: `./emulator/run-scenario.sh emulator/scenarios/<name> [timeout_ms]`. It rebuilds `firmware-bundle.uf2` from `firmware/dev/` with that config, runs `wokwi-cli --scenario`, fails on `Traceback`, and exits 0 when every step passed, nonzero otherwise (42 if `--timeout` hits first; a `wait-serial` that never matches usually ends at Wokwi's 5-minute connection limit instead, exit 1). A run is about 70 s and uses Wokwi cloud minutes.

How to write one:

1. Press parts wired in `diagram.json`: `btn_enc` = encoder push (GP0, switch 0, logical button 11), `btn1` = footswitch 1 (GP1), `btn5` = Down (GP20), `btn6`-`btn10` = A, B, C, D, Up (GP9, GP10, GP11, GP18, GP19). Footswitches 2-4 are on GP23-GP25, which Wokwi can't wire.
2. To test several setups in one run (one run = one config), put each on its own page and give a wired footswitch `type: "page_inc"` on every page. `encoder-push` uses footswitch 10 (`btn10`).
3. **Wait right after the action that prints.** `wait-serial` only sees text printed after the step starts, so `press → wait-serial → release → wait-serial` works, but a `wait-serial` after a `delay` hangs: the line already went by, and the run stalls until Wokwi's 5-minute connection limit (about 5 cloud minutes wasted). To test a long press, press and then wait for the long entry's line; the wait lets time pass.
4. Run `python3 -m pytest tests/test_wokwi_scenarios.py` before spending minutes (CI also runs it on every push). It replays every scenario on the desktop firmware harness with the same timing rule, so a wait that would hang fails there instantly. See [`tests/AGENTS.md`](../tests/AGENTS.md).

In CI, `.github/workflows/wokwi.yml` runs every scenario on Wokwi, but only when a non-draft PR touching `firmware/dev/` or `emulator/` is opened, a draft is marked ready, the `wokwi` label is added (remove and re-add to rerun), or it's started from the Actions tab. It needs the `WOKWI_CLI_TOKEN` repo secret; without it the job warns and passes. Serial logs are uploaded as the `wokwi-serial-logs` artifact.

Scenarios:

| Name | Checks |
|---|---|
| `encoder-push` | The STD10 encoder push works like a footswitch: legacy momentary CC 14, CC+ sharing a value with footswitch 1, PC + Also send note, a select group handed over between footswitch 1 and the push, keytimes short and long |

## Directory layout

```
emulator/
├── build-uf2.py          # Builds all-in-one UF2 (requires pyfatfs)
├── setup.sh              # Downloads CP UF2, runs build-uf2.py
├── test.sh               # wokwi-cli automated test
├── run.sh                # wokwi-cli interactive mode
├── run-scenario.sh       # Build with a scenario's config, run its steps, check serial
├── scenarios/            # One directory per scenario (config.json + scenario.yaml)
├── wokwi.toml            # Points firmware at firmware-bundle.uf2
├── diagram.json          # STD10 hardware model for Wokwi simulator
├── test-boot.yaml        # Early button-press scenario (no serial checks; see scenarios/)
├── configs/              # Test configs using correct firmware schema
├── firmware-bundle.uf2   # Generated — gitignored
└── circuitpython.uf2     # Downloaded — gitignored
```

## What it can and cannot test

**Can test:** firmware boot, config loading/parsing, device detection, button/encoder/expression init, MIDI message sending, display init (font loading), main loop execution.

**Cannot test:** NeoPixel/display visual rendering, GP23/24/25 buttons (internal Pico pins not exposed in Wokwi), real USB MIDI communication. MIDI is checked through the `[MIDI TX]` serial lines, not the USB port.

## Gotchas

- **`wokwi-cli` requires `firmware` field** in `wokwi.toml` — hard requirement for CircuitPython
- **GP23, GP24, GP25 are not available** on Wokwi's `wokwi-pi-pico` — valid pins are GP0–GP22 and GP26–GP28. The MIDI Captain PCB uses these internal pins for 3 switches; they can't be wired in the diagram but the firmware runs fine (switches float HIGH with pull-ups)
- **NeoPixel part type** is `wokwi-neopixel`; pins are `DIN`/`DOUT`/`VDD`/`VSS` (not `VCC`/`GND`)
- **CircuitPython filesystem is read-only from serial** — `storage.remount()` fails with `Cannot remount '/' when visible via USB` unless called from `boot.py` before USB init. This is why file injection via mpremote/REPL doesn't work.
- **`pyfatfs` API**: must create the image file first (`f.truncate(size)`), then call `PyFat.mkfs()`, then open with `PyFatFS()`. There is no `create=True` parameter.
- **UF2 block renumbering**: when concatenating two UF2s, all `block_no` and `total_blocks` fields must be rewritten across both halves
- **`wait-serial` only matches text printed after the step starts** — see Scenarios. A miss isn't reported until Wokwi's 5-minute connection limit on the free plan, regardless of `--timeout`.
- **Free tier**: 50 CI minutes/month — sufficient for weekly runs, not per-push. Pro is $25/seat/mo for 2,000 minutes.
- **`rp2040js-circuitpython` is a dead end** — has no CLI argument parsing, no `--image`/`--fs` flags, no filesystem injection. PR #33 was based on non-existent features.
