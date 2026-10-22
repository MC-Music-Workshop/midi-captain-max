# MIDI Learn over a serial command channel (#54)

- **Date**: 2026-10-21
- **Status**: Design. Not implemented.
- **Related**: #54, [close-out plan Phase 5](./2026-10-16-close-out-in-flight-work.md#phase-5-54-midi-learn-rework-editor--firmware), spike branch `54-learn-spike` (`c02815f`, `ea6a81a`), superseded first attempt on `54-midi-learn` (`174415b`)

## Problem

Setting a button up to match a host means copying a type, channel and number from the host's MIDI settings into the editor by hand. Users want to click **Learn**, move a control on the host, and have the button fill itself in.

The first attempt (`174415b` on `54-midi-learn`) read the `[MIDI RX ...]` lines that `code.py` printed for every incoming message. #206 turned those prints off by default (`MIDI_RX_LOG = False`), because each one costs several milliseconds over USB CDC and capped how much MIDI the pedal could absorb. So that approach no longer has anything to read, and turning the prints back on would undo #206.

## Decisions already made

These were settled in the close-out plan and aren't reopened here:

- **The editor asks, the pedal answers.** The editor sends an explicit start-learn command over the serial console it already uses for Save & Restart. The pedal replies with one structured line per event. The editor merges the result into the form as an unsaved change, and the normal save path validates and writes `config.json`. The pedal never writes files.
- **Learning is one-shot.** The first learnable message ends learning.
- **A captured message is only reported** (pre-mortem 4, decided 2026-10-18). The pedal doesn't act on it: no page switch, no LED change.
- **Two Learn actions** (pre-mortem 6, decided 2026-10-18). **Learn** sets what the button sends (type, channel, number). **Learn listen** writes `cc_receive`.

## What the user sees

**Learn (send)**

1. On a button, click **Learn**. It changes to **Listening… ✕**.
2. Send a CC, note or program change from the host to the pedal.
3. The button's **Type**, **Channel** and **CC** / **Note** / **Program** fill in. The footer says what was learned, for example `Button 3: learned CC 20 on Ch 1 (USB)`.
4. The change is unsaved, like any other edit. **Save** writes it; **Undo** reverts it.

**Learn listen**

Same flow, from a small **Learn** button next to **Listen CC**. Only a CC ends it; the pedal ignores notes and program changes while waiting (they're handled normally). The result fills **Listen CC** and nothing else.

**Cancelling and failing**

- Clicking **Listening… ✕** cancels. Clicking **Learn** on another button moves learning there.
- After 30 seconds with nothing learnable, Learn stops and the footer says no MIDI arrived, with the routing hint below.
- On firmware without Learn, the footer says within about a second that the pedal's firmware doesn't support MIDI Learn and to update it.

## Protocol

Plain ASCII lines over the existing serial console, at the existing 115200 baud. The editor writes; `code.py` reads with a non-blocking poll in the main loop. There's no REPL involved and nothing is echoed.

### Commands (editor → pedal)

| Command | Meaning |
|---|---|
| `LEARN` | Arm learning for the first CC, note-on or program change. |
| `LEARN CC` | Arm learning for the first CC only (**Learn listen**). |
| `LEARN STOP` | Disarm. Harmless when not armed. |

- Lines end in `\n`; the pedal strips surrounding whitespace, so `\r\n` works too.
- Unknown lines are ignored silently. Printing an error would cost a console write for every junk line a serial monitor sends.
- A second `LEARN` while armed re-arms with the new filter and restarts the timeout.
- The editor never sends `0x03` (Ctrl-C) or `0x04` (Ctrl-D) as part of Learn. Those still mean "stop and reload" to CircuitPython, and the existing restart and installer paths depend on that.

### Replies (pedal → editor)

| Reply | When |
|---|---|
| `[LEARN] on` or `[LEARN] on cc` | Right after `LEARN` / `LEARN CC`. Acts as the capability handshake. |
| `[LEARN] {json}` | A learnable message arrived. Learning is now off; no separate `off` line follows. |
| `[LEARN] off` | After `LEARN STOP`. |
| `[LEARN] off timeout` | 30 s passed with nothing learnable. |

The JSON is shaped like the matching fields of a button config, plus two informational keys:

```text
[LEARN] {"type": "cc", "channel": 0, "cc": 20, "value": 127, "source": "USB"}
[LEARN] {"type": "note", "channel": 2, "note": 60, "value": 100, "source": "DIN"}
[LEARN] {"type": "pc", "channel": 0, "program": 4, "source": "USB"}
```

- `channel` is 0–15, the config's encoding.
- `value` is the CC value or note-on velocity. The editor doesn't write it (see **What gets written**).
- `source` is `USB` or `DIN`.

Other console output (`[PAGE]`, `[CONFIG WARN]`, dev-mode stats) can arrive interleaved; the editor ignores every line that doesn't start with `[LEARN] `.

## Firmware

### Reading the console

The spike measured three ways to read input on CircuitPython 7.3.1 and settled on one:

- **Use** `usb_cdc.console.in_waiting` and one `usb_cdc.console.read(n)` per pass. It's non-blocking and reads in bulk.
- **Not** `supervisor.runtime.serial_bytes_available`: on CP 7 it's a bool, not a count.
- **Not** `sys.stdin.read(1)`: about 1 ms per byte, so a 64-byte burst blocked the loop for about 54 ms.

Rules for the poll, called once per main-loop pass before `handle_midi()`:

- If `usb_cdc.console` is `None`, skip. `boot.py` doesn't disable it today, but the check costs nothing.
- Read at most 64 bytes per pass, so a serial monitor pasting kilobytes can't stall switch scanning. (The spike read everything at once and spent 284 ms on 4 KB.)
- Keep a line buffer capped at 64 bytes. If it fills without a newline, drop it: no command is that long.
- Keep only printable ASCII bytes before decoding: commands are ASCII, and CircuitPython's `bytes.decode()` can raise on invalid UTF-8 (it doesn't honor `errors=`). Junk bytes must never raise.

### Arming and capture

- `LEARN` sets a learn filter (`any` or `cc`) and a deadline 30 s out, then prints `[LEARN] on` (or `[LEARN] on cc`).
- The capture check sits at the top of `_process_midi_msg`. That's the point where a message has already passed the routing matrix's "→ This pedal" switch for its input. **Learn hears exactly what the pedal hears**: an input routed away from the pedal can't be learned from, which keeps one rule for users and for the troubleshooting text.
- A **learnable** message is a CC, a note-on with velocity above 0, or a program change, and it must match the filter. When one arrives while armed, the pedal:
  1. prints `[LEARN] {json}`
  2. disarms
  3. returns without running the rest of `_process_midi_msg`. No page switch, no LED or select-group change, no status line (pre-mortem 4).
- Anything else processes normally while armed: note-offs, note-on with velocity 0, clock, SysEx, pitch bend, and notes or PCs under `LEARN CC`. The pedal keeps following the host for everything it isn't learning.
- MIDI Thru is untouched. The captured message is still forwarded downstream if the routing matrix says so. Learning changes what the pedal does, not what it passes through.
- The deadline is checked once per pass against `time.monotonic()`. When it expires, the pedal disarms and prints `[LEARN] off timeout`.

The firmware-side timeout is the safety net that matters for live use. If the editor crashes or the cable is pulled mid-learn, the pedal is disarmed within 30 s. Otherwise it would swallow the first page change or button-sync message on stage. A soft reload or power cycle also clears it, since learn state is RAM only.

### Code layout

- **`firmware/dev/core/learn.py`** (new, pure, unit-tested): line splitting with the 64-byte cap, command parsing (`LEARN`, `LEARN CC`, `LEARN STOP` → action), the learnable check, and building the reply dict from `(kind, channel, number, value, source)`. It has no `usb_cdc` or `adafruit_midi` imports, so it runs under pytest like `midi_rx.py` and `cc_step.py`.
- **`code.py`** glue: the console poll, the armed state and deadline, the capture hook in `_process_midi_msg`, and the `print`.

### Cost

The spike's idle loop ran at about 410 passes per second with the poll in place, but there was no baseline without it. The implementation bench (below) measures both and accepts the change if the idle rate drops by less than 5%. If it costs more, poll every Nth pass instead. A rate drop that small doesn't affect switch latency.

## Editor

### Rust: `midi_learn.rs`

Keep the command shape from `54-midi-learn`, with a new argument and a rewritten reader:

- `learn_midi(path, mode)`, where `mode` is `"send"` or `"listen"`. It returns the learned message, or `None` when cancelled.
- `cancel_midi_learn()`.

Sequence inside `spawn_blocking`:

1. `verify_device_connected`, then `open_device_serial` (no Ctrl-C), with a 100 ms read timeout so cancel is noticed quickly.
2. Clear the input buffer so stale console output can't be mistaken for a reply.
3. `write_all` the command plus `\n`, then `flush`. Partial writes are the trap the spike hit with non-blocking writes; `write_all` on the blocking port handles it.
4. Wait up to 1 s for `[LEARN] on`. If it doesn't arrive, return the "firmware doesn't support MIDI Learn, or isn't running" error. That covers old firmware and a crashed `code.py` sitting at the REPL. The REPL just raises a harmless `NameError` on `LEARN`.
5. Read lines until one of these:
   - `[LEARN] {json}` → parse with `serde_json` into `LearnedMidi` and return it.
   - `[LEARN] off timeout` → return the "no MIDI received" error.
   - cancel requested → write `LEARN STOP\n`, wait up to 500 ms for `[LEARN] off`, return `None`.
   - an editor-side deadline of 35 s → return the same error as a pedal timeout. This is a fallback; the pedal normally times out first.
   - a read error other than timeout → "Lost the device's serial connection".

Keep the byte-level line assembly from the old reader (decode only complete lines, cap pending bytes at 4 KB), since a read can split a multi-byte button label in other console output.

Version checks against `VERSION.txt` were considered and rejected. Dev builds report versions like `v1.14.0-3-g3440027`, and the 1 s handshake answers the real question ("does this firmware speak Learn?") directly.

### Which pedal (pre-mortem 8)

`open_device_serial` already refuses to guess. With two or more Adafruit serial ports it fails with "Found N CircuitPython devices. Disconnect other devices and try again." Learn inherits that, so with two pedals connected it errors clearly instead of arming the wrong pedal. Matching a drive to its own serial port belongs with the unique volume ID work in close-out Phase 8; when that lands, Learn gets multi-pedal support for free.

### One serial user at a time (pre-mortem 9)

`serialport` opens the port exclusively, so while Learn is listening, Save & Restart, Restart, the firmware installer and bootloader entry can't open it.

- Each of those actions first calls `cancelLearn()` and waits for it to finish (≤ about 600 ms: one read timeout plus the `off` wait). They then open the port as they do today. One rule, applied at those call sites: **anything that opens the serial port cancels Learn first**.
- If another program holds the console (`screen`, `tio`), `open_device_serial` fails; the footer shows that error plus "close any serial monitor".

### Form mapping: `midiLearn.ts`

Keep `learnedFieldUpdates()` from `54-midi-learn` for **Learn (send)**, with one change:

| Learned | Writes |
|---|---|
| CC | `type: "cc"`, `channel`, `cc` |
| Note | `type: "note"`, `channel`, `note` |
| PC | `type: "pc"`, `channel`, `program` |

- **Channel follows the global channel** (pre-mortem 3). If the learned channel equals `global_channel`, clear the button's `channel` instead of setting it, so the button keeps following the global channel. Otherwise set it.
- **Identity only.** `cc_on`/`cc_off` and velocities stay as configured. One incoming `127` or velocity says nothing about what the on and off values should be.
- **Mode stays valid.** If the button's mode doesn't exist for the new type, it becomes `toggle` (`flash` is PC-only, `select` is CC/PC-only). Same as the first attempt.

**Learn listen** adds `learnedListenUpdates()`:

- It writes `cc_receive` = the learned CC. If that equals the button's `cc`, it clears `cc_receive` instead. The firmware validator already drops a `cc_receive` equal to `cc`, so the form matches what the pedal will run.
- It never changes `channel`. If the CC arrived on a different channel from the button's effective channel, the footer warns: `learned Listen CC 21, but it arrived on Ch 5 and this button listens on Ch 1`. Silently moving the channel would also change what the button sends.

### Where Learn is offered (pre-mortem 7)

| Button | Learn (send) | Learn listen |
|---|---|---|
| `type` cc, note or pc; mode toggle, momentary, flash or select | Yes | Only for cc, next to **Listen CC** |
| `mode: "keytimes"` | No | No |
| `cc_inc`/`cc_dec`, `pc_inc`/`pc_dec`, `hid`, page types | No | No |

- A keytimes button's messages live in its cycle entries, and step buttons share a value keyed by CC. A single learned identity doesn't map onto either cleanly.
- To learn onto an HID or page button, switch its type to CC, Note or PC first. That keeps Learn from silently turning a page button into a CC button.
- Keytimes **Listen CC** fields (#211) are a natural later addition, using the same `LEARN CC` command.

### Display (pre-mortem 5)

Programs show as stored (0–127), the same as the editor's **Program** field: `learned PC 4 on Ch 1`. Some hosts count programs from 1, so the user guide gets one line about it. Changing the editor's numbering everywhere is out of scope.

### Rows and pages

Keep the first attempt's guard: rows are keyed by position, so a result that arrives after a page switch is discarded instead of landing on the other page's button. Switching pages cancels Learn.

## Pre-mortem coverage

| # | Report | Answer |
|---|---|---|
| 1 | Learn times out with no reason on old firmware | 1 s handshake → "firmware doesn't support MIDI Learn" |
| 2 | Learned the wrong CC because host feedback arrived first | One-shot makes retry cheap; the result is an unsaved change; the guide says to pause host feedback while learning |
| 3 | Button stopped following `global_channel` | `channel` cleared when it equals the global channel |
| 4 | Learning a page CC switched the page | Captured message only reported, not acted on |
| 5 | "Sent program 5, learned 4" | Shown as stored, like the Program field; guide note |
| 6 | Learned the send CC, wanted the listen CC | Separate **Learn listen**, CC-only via `LEARN CC` |
| 7 | Learn on keytimes or CC+/CC- did nothing useful | Not offered there |
| 8 | Learned onto the wrong pedal | Existing multi-port refusal; full fix with Phase 8 |
| 9 | "Port busy" / Save during learning | Serial users cancel Learn first; clear error for external monitors |
| 10 | 14-bit/NRPN learns CC 99; crashed `code.py` | Accepted; the handshake reports the crashed case |

## Tests

### Firmware (pytest, `tests/test_learn.py`)

- **Line splitting:** commands split across reads; `\r\n` and `\n`; the 64-byte cap drops an over-long line and recovers on the next newline; junk bytes don't raise.
- **Commands:** `LEARN`, `LEARN CC`, `LEARN STOP`, surrounding whitespace, unknown lines ignored.
- **Learnable check:** CC, note-on > 0 and PC under `any`; only CC under `cc`; note-on velocity 0, note-off, clock and pitch bend never.
- **Reply dict:** exact keys and values for each type, 0-based channel, `source`.

### Editor

- **Rust `midi_learn.rs`:** the reader against a scripted fake port:
  - handshake success, and a missing handshake → firmware error
  - result line split across reads and interleaved with `[PAGE]` / multi-byte label lines
  - `off timeout` → error
  - cancel sends `LEARN STOP`
  - malformed JSON is ignored and reading continues
  - the bytes written are exactly `LEARN\n` or `LEARN CC\n`, never `0x03`/`0x04`
- **TS `midiLearn.test.ts`:**
  - send mapping per type
  - channel cleared when equal to global
  - mode reset for flash/select
  - listen mapping, including `cc_receive` cleared when equal to `cc`
  - the channel-mismatch warning
- **Offered-where:** a component test or table test that the Learn buttons appear only for the rows in the table above.

### Bench: `tools/bench/learn.py` (new, added to `run.sh`)

Same style as `serial-stall.py`: stdlib only, `sendmidi` for MIDI, raw serial, uses the existing `nano4-207-serial-din-test.json` config (page_control jump on CC100, Ch 4).

1. Handshake: `LEARN` → `[LEARN] on` within 1 s.
2. For each of USB and DIN: send CC 20, note 60, PC 4 (re-arming each time) and check each `[LEARN]` JSON line.
3. **Page CC is not acted on:** arm, send CC100 value 1, and check the JSON line arrives with no `[PAGE]` line after it. Then send CC100 value 1 unarmed and check the `[PAGE]` line does appear.
4. **Filter:** `LEARN CC`, send a note then a CC, and check only the CC is reported.
5. **Timeout:** arm with nothing sent, and check `[LEARN] off timeout` arrives at 30 s (±1 s).
6. **Stop:** arm, `LEARN STOP`, check `[LEARN] off`, then send a CC100 and check the page switches.
7. **Junk:** write 4 KB of random printable bytes, then `LEARN` still gets a handshake; a footswitch press during the junk still sends.
8. **Loop cost** (manual, recorded once in the PR): idle passes per second in dev mode on `main` firmware vs the Learn firmware, accepting a drop under 5%.

### Bench: manual, in the editor

- Learn and Learn listen over USB and DIN on a NANO4, then **Save & Restart** while listening, then the installer while listening.
- Old firmware (v1.14.0): Learn reports "doesn't support" within about a second. Then **Save & Restart** and a firmware install both still work. This is the one case where `LEARN\n` sits unread in the pedal's input buffer when the next Ctrl-C arrives; it should be harmless (one stray `NameError` at the REPL), but it needs checking on hardware.

## Documentation

- Rewrite `docs/user/midi-learn.md` (from `54-midi-learn`): add Learn listen, the global-channel behavior, the program numbering note, "pause host feedback while learning", and the routing and serial monitor troubleshooting.
- `config-editor/AGENTS.md`: replace the first attempt's section with the protocol, the "serial users cancel Learn first" rule, and the handshake.
- `firmware/AGENTS.md`: the console poll (why `in_waiting` + `read(n)`, the 64-byte caps), and that `[LEARN]` lines are a contract with `midi_learn.rs`.
- `docs/bench-tests.md`: the new `learn.py` test.

## Out of scope

- Learning onto keytimes entries, step buttons, encoders or expression pedals.
- Learning on/off values or velocities.
- Multi-pedal port selection (Phase 8).
- Writing config from the pedal.
