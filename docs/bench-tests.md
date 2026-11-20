# Bench Tests

Hardware tests that run against a real pedal from a Mac. The automated ones live in `tools/bench/` and print `PASS`/`FAIL`; the manual ones are judged by watching the LEDs.

**How:** run the whole automated suite and get a markdown table for the release notes:

```bash
tools/bench/run.sh              # NANO4
tools/bench/run.sh --gap 0.4    # STD10: it redraws a page more slowly
```

Run it before tagging a firmware release (see [`.github/AGENTS.md`](../.github/AGENTS.md#release-process)).

---

## Setup

You need:

- `sendmidi` and `receivemidi`: `brew install gbevin/tools/sendmidi gbevin/tools/receivemidi`
- A USB-to-DIN MIDI cable (the tests expect the port name `USB MIDI Interface`; override with `--din-port`)
- **One** pedal connected. Every MIDI Captain enumerates under the same port name (`Pico Midi Captain- usb_midi.ports[0]`), so a second pedal makes the target ambiguous.

Wiring: pedal on USB the whole time; USB-to-DIN cable **OUT** into the pedal's **MIDI IN**.

### Putting a bench config on the pedal

Each test names the config it needs; they live in [`tools/bench/configs/`](../tools/bench/configs/).

**How:**

1. Unplug the pedal. Hold the top-left switch (switch 1 / `KEY0`) while plugging in USB. Performance mode hides the drive; the held switch mounts it.
2. Copy the bench config onto the drive as `config.json`:

   ```bash
   cp tools/bench/configs/nano4-207-serial-din-test.json /Volumes/<drive>/config.json
   ```

3. Eject the drive, then unplug and replug USB **without** holding a switch.

| Config | Used by | What it has |
|--------|---------|-------------|
| `nano4-207-serial-din-test.json` | `din-count.sh`, `serial-stall.py`, `run.sh` | 2 pages × 4 note toggles (notes 60–63, Ch 4 via `global_channel: 3`), `page_control` jump on CC100, `off_mode: off` |
| `std10-207-serial-din-test.json` | Same as above, on an STD10 | The NANO4 config's 2 pages with 10 note toggles each (notes 60–69), expression inputs off (empty jacks drift and send CCs, #160), `dev_mode` on so the drive stays mounted |
| `nano4-200-keytimes-rx-test.json` | Manual keytimes host-sync check | Two `keytimes` buttons with `short_cc_receive`/`long_cc_receive`, a CC toggle, a note toggle |

On another device, change `device` and adjust the button count; `tests/test_bench.py` checks every file in `configs/` against `config.schema.json` and the firmware validator.

---

## Automated tests

All scripts take `--pedal-port NAME` (and `--din-port NAME` where DIN is involved). Run `sendmidi list` to see port names. Each prints one `PASS ...` or `FAIL ...` line last and exits nonzero on `FAIL`.

The scripts send every message through one long-running `sendmidi dev <port> --` process (`--` reads commands from stdin). On macOS 27.2, starting a new MIDI client fails every ~10 s (CoreMIDI error -304, "Couldn't find MIDI output", then a ~5 s stall), so one `sendmidi` per message makes the tests fail with no pedal fault. It happens with no pedal attached (IAC Driver bus) and with a minimal CoreMIDI program, so it's the OS, not `sendmidi`. Run one-off `sendmidi`/`receivemidi` commands by hand as usual, but keep repeated sends in one process.

### DIN receive count (`din-count.sh`)

Checks that the pedal receives every message on its DIN MIDI IN while busy repainting. Sends `N` (default 100) alternating note 60 on/off on Ch 4 through the DIN cable and counts what the pedal forwards back over USB via its default-on DIN→USB thru. Every note toggles button 1, so every message forces a repaint.

- `paced`: one message every 60 ms (control)
- `burst`: all `N` in one `sendmidi` call, back to back at 31250 baud

**How:**

```bash
tools/bench/din-count.sh          # N = 100
tools/bench/din-count.sh 500
```

**Pass:** `paced N/N` and `burst N/N`. Fails fast if either MIDI port is missing.

### Serial console stall (`serial-stall.py`)

Checks that a serial console left open but unread (like a suspended `screen`) doesn't slow down or wedge the pedal. Flips pages via `page_control` CC100 (jump 0/1) once per 0.25 s, so the pedal prints one `[PAGE]` line per flip, and watches every send for errors or blocking.

- `read`: keeps reading the console (baseline; default 200 flips, ~1 min)
- `hold`: opens the console and never reads, then drains at the end (default 2000 flips, ~8 min: enough to overflow the host's buffer). Then it probes: 10 more flips 1 s apart while reading the console. A wedged pedal prints none of them.

**How:**

```bash
python3 tools/bench/serial-stall.py read
python3 tools/bench/serial-stall.py hold
python3 tools/bench/serial-stall.py hold --flips 3000 --serial /dev/cu.usbmodem1101
```

Close `screen` and the Config Editor's serial console first. If page changes arrive faster than the pedal redraws a page, it merges them: no `[PAGE]` line, same final page. Keep `--gap` at 0.25 s or more on a NANO4 and 0.4 s on an STD10, which merges below ~0.35 s (0.3 s: 80/100 lines; 0.35 s: 100/100). During a `hold` run you can also press a footswitch to confirm the pedal still responds.

**Pass:** no send that failed or blocked over 0.2 s; in `read` mode also `[PAGE]` lines == flips (±2, `--tolerance`); in `hold` mode the probe's `[PAGE]` lines == 10 (±2). The `hold` run's own line count and bytes buffered are informational.

---

## Baseline results

Device NANO4, macOS, 2026-10-17.

| Test | Firmware | Result |
|------|----------|--------|
| DIN receive count, paced | `receiver_buffer_size=64` | 100/100 |
| DIN receive count, burst | `receiver_buffer_size=64` | 52, 53, 52 of 100 (three runs): **FAIL** |
| DIN receive count, burst | `receiver_buffer_size=512` | 100/100 (four runs). Draining the burst takes ~5.7 s (~57 ms per repainting note, see #208) |
| Serial console stall, `hold` | per-event prints on (`main` at `f8ddd56`) | No stall. macOS buffered ~44.9 KB (1,726 lines), then dropped the rest; the pedal kept flipping pages |

Device STD10, macOS 27.2, 2026-11-07, firmware `v1.15.0-beta.3` (same commit as `v1.15.0`), `std10-207-serial-din-test.json`, `run.sh --gap 0.4`.

| Test | Result |
|------|--------|
| DIN receive count | PASS: paced 100/100, burst 100/100 |
| Serial console stall, `read` | PASS: 200 flips, 200 `[PAGE]` lines, 0 failed sends |
| Serial console stall, `hold` | PASS: 2000 flips, 0 failed sends, probe 10/10. macOS 27.2 kept all 2,000 lines (77 KB) and delivered them within ~0.5 s of reading. A separate check during a hold: DIN→USB thru answered all 40 pings, slowest 93 ms, the same as with the console read |
| One `sendmidi` per message (before this change) | `read` and `hold` FAIL from the host: a failed send every ~10 s, then a ~5 s stall. DIN receive count still passed |

Linux and Windows hosts are untested.

---

## Manual tests

These need a person watching the LEDs or display.

### MIDI RX flood (`tools/visibox-flood.sh`)

Simulates Visibox omni-mode LED feedback (#205): notes 60–69 on all 16 channels every ~300 ms, plus 3× bursts on each clip change.

**How:**

```bash
tools/visibox-flood.sh "Pico Midi Captain- usb_midi.ports[0]" 30
```

**Pass:** the LEDs follow the playing clip without lag, settle on the last note within a moment of the flood stopping, then stay still. `Rejected sends: 0`.

### Keytimes host sync (#200)

Checks that when the host sets a `keytimes` button's state, the next press fires the entry *after* the host's, not the same one again. Needs `nano4-200-keytimes-rx-test.json`.

**How:** watch what the pedal sends in one terminal, set state from another:

```bash
receivemidi dev "Pico Midi Captain- usb_midi.ports[0]"
sendmidi dev "Pico Midi Captain- usb_midi.ports[0]" ch 4 cc 20 0    # KT1 short -> S-OFF
```

**Pass:**

- After `cc 20 0`, KT1 shows `S-OFF` and a short press sends CC20 127 (`S-ON`).
- After `cc 21 64`, KT1 shows `L-B` and a long press sends CC21 127 (`L-C`).
- After `cc 24 20`, KT2 shows `P2` and a press sends CC24 30 (`P3`).
