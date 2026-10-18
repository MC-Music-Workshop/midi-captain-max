# Bench Tests

Hardware tests that run against a real pedal from a Mac. The automated ones live in `tools/bench/` and print `PASS`/`FAIL`; the manual ones are judged by watching the LEDs.

**How:** run the whole automated suite and get a markdown table for the release notes:

```bash
tools/bench/run.sh
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
| `nano4-200-keytimes-rx-test.json` | Manual keytimes host-sync check | Two `keytimes` buttons with `short_cc_receive`/`long_cc_receive`, a CC toggle, a note toggle |

The configs target the NANO4. On another device, change `device` and adjust the button count; `tests/test_bench.py` checks every file in `configs/` against `config.schema.json` and the firmware validator.

---

## Automated tests

All scripts take `--pedal-port NAME` (and `--din-port NAME` where DIN is involved). Run `sendmidi list` to see port names. Each prints one `PASS ...` or `FAIL ...` line last and exits nonzero on `FAIL`.

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

Checks that a serial console left open but unread (like a suspended `screen`) doesn't slow down or wedge the pedal. Flips pages via `page_control` CC100 (jump 0/1) once per 0.25 s, so the pedal prints one `[PAGE]` line per flip, and times every send.

- `read`: keeps reading the console (baseline; default 200 flips, ~1 min)
- `hold`: opens the console and never reads, then drains at the end (default 2000 flips, ~8 min: enough to overflow the host's buffer)

**How:**

```bash
python3 tools/bench/serial-stall.py read
python3 tools/bench/serial-stall.py hold
python3 tools/bench/serial-stall.py hold --flips 3000 --serial /dev/cu.usbmodem1101
```

Close `screen` and the Config Editor's serial console first. Keep `--gap` at 0.25 s or more: faster, and the pedal merges page changes into one `[PAGE]` line. During a `hold` run you can also press a footswitch to confirm the pedal still responds.

**Pass:** no send slower than 0.2 s or failed; in `read` mode also `[PAGE]` lines == flips (±2, `--tolerance`). In `hold` mode the line count and bytes buffered are informational.

---

## Baseline results

Device NANO4, macOS, 2026-10-17.

| Test | Firmware | Result |
|------|----------|--------|
| DIN receive count, paced | `receiver_buffer_size=64` | 100/100 |
| DIN receive count, burst | `receiver_buffer_size=64` | 52, 53, 52 of 100 (three runs): **FAIL** |
| DIN receive count, burst | `receiver_buffer_size=512` | 100/100 (four runs). Draining the burst takes ~5.7 s (~57 ms per repainting note, see #208) |
| Serial console stall, `hold` | per-event prints on (`main` at `f8ddd56`) | No stall. macOS buffered ~44.9 KB (1,726 lines), then dropped the rest; the pedal kept flipping pages |

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
