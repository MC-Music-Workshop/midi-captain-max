# Emulator Hardware Tests (Wokwi)

Headless, automated hardware tests for the firmware — runs the **real**
CircuitPython 7.3.3 firmware on a simulated RP2040 (Wokwi cloud), presses
simulated footswitches, and asserts on the MIDI the firmware emits.

Runs as the `hardware-test` matrix job in `.github/workflows/release.yml` on every
`v*` release tag, and locally. It is currently **non-blocking**: each device's
pass/fail is reported to the workflow run summary, but a failure does not stop the
release (flip by removing `continue-on-error` in the job — see the `release.yml`
comment). Also runnable locally.

## What it tests

For each device variant, a scenario boots the firmware, confirms device
detection, then presses buttons and asserts the resulting serial output:

- Firmware boots and detects the device from `config.json`
- Config loads (buttons, encoder, expression, fonts, display)
- A **toggle** button press emits `CC=127`, the next press emits `CC=0`
- A **momentary** button press emits `CC=127`, release emits `CC=0`
- No Python `Traceback` anywhere in the run

**Cannot test:** NeoPixel/display visual rendering, switches on internal Pico
pins (see *wirable pins* below), real USB-MIDI/HID transport.

## How it works

`wokwi-cli` uploads a UF2 to Wokwi's cloud and streams serial back. The CLI does
**not** inject project files into CircuitPython's flash (a browser-only feature),
so `build-uf2.py` bakes the firmware into an **all-in-one UF2**: the CP runtime
concatenated with a FAT12 image holding `code.py`, `boot.py`, `config.json`,
`core/`, `devices/`, `lib/`, `fonts/`. The firmware files come straight from
`firmware/dev/` (the same tree `deploy.sh` ships), so the emulator runs what users
run — only the *config* is swapped for a deterministic per-device test config.

The firmware prints a parseable line for every event it sends, e.g.
`[MIDI TX] Ch1 CC20=127 (switch 1, toggle)` — that serial output is the whole
basis for action→outcome testing.

**Where the assertions live.** The scenario YAML (`scenarios/<device>.yaml`) only
*drives inputs*: it waits for the boot banner, then presses footswitches via
`set-control` with delays. The MIDI assertions are done *post-hoc* by `test.sh`,
which greps the captured serial log for every line in `scenarios/<device>.expected`.
This is deliberate: wokwi-cli's `wait-serial` only matches serial that arrives
*after* the step starts, so it cannot reliably catch a press-triggered line (the
emit races the step) — but it *is* reliable for the boot banners (the wait is
active from sim start). Driving inputs in the scenario and asserting against the
log afterwards sidesteps the race entirely and makes assertions deterministic.

## Usage

```bash
pip install pyfatfs                          # one-time
export WOKWI_CLI_TOKEN=your_token            # from https://wokwi.com/dashboard/ci

./emulator/test.sh std10                     # one device: std10 | mini6 | nano4
./emulator/test-all.sh                       # all device variants in sequence
./emulator/run.sh std10                      # interactive (stream serial, Ctrl+C)
```

`test.sh` is self-contained: it downloads the CP runtime UF2 if missing, builds
the per-device bundle, and runs that device's scenario. Exit 0 = pass, 1 = fail.

## Layout

```
emulator/
├── _common.sh             # shared helpers (wokwi-cli finder, CP UF2 download)
├── build-uf2.py           # builds the all-in-one UF2 (--config <path>)
├── setup.sh               # download CP UF2 + build one device bundle
├── test.sh [device]       # build + run one device's hardware test
├── test-all.sh            # run every device variant
├── run.sh [device]        # interactive
├── wokwi.toml             # points firmware at firmware-bundle.uf2
├── diagram-<device>.json  # per-device Wokwi hardware model
├── configs/test-<device>.json    # deterministic per-device test config
├── scenarios/<device>.yaml       # per-device scenario: boot waits + footswitch presses
└── scenarios/<device>.expected   # serial lines test.sh greps for (the assertions)
```

Generated/downloaded files (`*.uf2`, `*.img`, `*.log`, staged `diagram.json`) are
gitignored.

## Gotchas

- **`wait-serial` only matches serial that arrives AFTER the step starts** — it is
  not retroactive, and it cannot reliably catch a press-triggered line (the emit
  races the step; sometimes it lands before `wait-serial` activates and is missed
  forever, hanging the run). This is *the* reason MIDI assertions are done by
  grepping the log post-hoc in `test.sh` rather than with scenario `wait-serial`.
  `wait-serial` is only used for boot banners, which are reliable because that wait
  is active from sim start, before the banner prints.
- **`.expected` matches are literal (`grep -F`), but `wait-serial` patterns are
  REGEX.** If you ever do add a `wait-serial` MIDI assertion, `[MIDI TX]` and
  `(switch 1, toggle)` are regex metacharacters — and a regex pattern is matched
  *anchored at the line start*, while a metachar-free pattern matches as a
  substring anywhere. (This asymmetry is why bare `wait-serial` MIDI patterns are
  so error-prone, and another reason the log-grep approach is used instead.)
- **Assert only lines unique to a test action.** Every *momentary* button emits
  `CC=0` once at boot (`Switch.last_state` initializes so the first poll looks like
  a release edge), so a momentary release `=0` can't be distinguished from boot by
  a substring grep — assert the momentary *press* `=127` instead (boot never emits
  `=127`). Toggle buttons are silent at boot, so both their `=127` and `=0` are safe
  to assert. (The boot `CC=0` burst is real MIDI the firmware sends on power-up —
  possibly worth a separate look, but out of scope for the test harness.)
- **`--scenario` is resolved relative to the project dir** argument, not your
  CWD. Pass `scenarios/std10.yaml`, not `emulator/scenarios/std10.yaml`.
- **`--diagram-file` is ignored** by wokwi-cli 0.26.1 (both `lint` and simulate) —
  it only ever reads `<projectdir>/diagram.json`. The scripts work around this by
  copying `diagram-<device>.json` to `diagram.json` (gitignored) before each run.
  A simulation with no `diagram.json` boots but wires no buttons, so presses
  silently never register — the tell-tale symptom of this trap.
- **Wirable pins.** Wokwi's `wokwi-pi-pico` exposes GP0–GP22 and GP26–GP28 only.
  GP23/24/25 (`board.LED`, `board.VBUS_SENSE`) are internal and **cannot be
  wired**, so switches on them are omitted from the diagrams and not asserted:
  STD10 switches 2/3/4, Mini6 switches 2/3, NANO4 switch 2. The firmware still
  runs fine — those inputs just float HIGH (never pressed).
- **`wokwi-cli` requires a `firmware` field** in `wokwi.toml` even for
  CircuitPython — it points at `firmware-bundle.uf2`.
- **CircuitPython's filesystem is read-only from serial** (`storage.remount`
  fails while USB-visible), which is why files are baked into the UF2 rather than
  pushed at runtime.
- **`pyfatfs` API**: create + `truncate(size)` the image file first, then
  `PyFat.mkfs()`, then open with `PyFatFS()`. No `create=True`.
- **UF2 block renumbering**: concatenating two UF2s requires rewriting every
  `block_no`/`total_blocks` field across both halves (`build-uf2.py` does this).
- **Cost**: Wokwi cloud, ~0.5 min per device run; free tier is 50 CI min/month.
  A full 3-device matrix release gate is ~1.5 min.
