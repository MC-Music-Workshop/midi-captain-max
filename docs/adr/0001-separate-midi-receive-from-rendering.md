# ADR 0001: Separate MIDI receive from rendering

- **Status**: Accepted (implementation pending)
- **Date**: 2026-10-15
- **Related**: #205, #206, #207, #208 (implementation), #54

## Context

Hosts that send a lot of MIDI can overwhelm the pedal. Visibox in omni mode resends every clip's LED state on all 16 channels several times a second. A clip start is a burst of about 480 messages (#205).

Before #206, the main loop handled one incoming message per pass. Every message that matched a button repainted it immediately: LEDs, TFT, and status label. Measured on a Mini6 over USB (#206):

| Build | Per message | 480-message burst clears in |
|---|---|---|
| `main` before #206 | ~10 ms (30–70 ms when a button repaints) | Never caught up under live traffic |
| #206 | ~3.2 ms | ~2 s |

The performer sees LEDs lagging behind the host, and they keep flashing after the host has stopped as the backlog replays stale states.

#206 fixes the immediate problem with four targeted changes:

- Drain up to 32 messages per pass.
- Skip the repaint for note messages that don't change a button's state.
- Turn off the per-message `[MIDI RX ...]` console prints.
- Make the DIN UART non-blocking.

Reviewing #206 turned up three limits of that approach:

- **Footswitch latency during a burst**: the switch scan waits while the pedal drains up to 32 messages. That's about 100 ms with cheap messages, and much longer when they repaint buttons (tens of ms each). A time cap (stop after ~10 ms) would bound this, but it treats the symptom: the expensive repaint is still happening inside the receive step.
- **Dedupe per message type**: #206 skips redundant repaints only for notes. Doing the same for CC with a "did the state change?" check would break `cc_receive` buttons. Their local press flips `ButtonState.state` without repainting, because the host owns the LED, so the host's confirming message would look redundant and get skipped, leaving the LED stale.
- **DIN overflow**: the DIN UART has a 64-byte receive buffer (`receiver_buffer_size=64`). At 31,250 baud a continuous stream fills it in about 20 ms, and a single repaint can take longer than that. Bytes that arrive after that are dropped. USB doesn't have this problem, because the host holds messages until the device is ready.

All three come from the same coupling: receiving a message and drawing its result happen in the same step.

CircuitPython 7.3.1 on the RP2040 gives the firmware a single cooperative main loop: no threads, and no access to the second core. Any fix has to come from how work is scheduled within that loop.

## Decision

Split the main loop's MIDI work into a cheap **receive** step that only updates state, and a frame-rate-limited **render** step that draws.

1. **Receive updates state only**: each incoming message updates the button's desired appearance (state, keytime index, slot value) and marks it dirty. No LED, TFT, or status-label writes. MIDI thru forwarding also stays here, since it's latency-sensitive. Receive drains whatever is waiting, with the batch cap kept only as a safety net.
2. **Render compares and draws at a fixed rate**: about 30 times a second, compare each button's desired appearance with what's currently displayed and repaint only the ones that differ. However many messages arrived in between, each changed button is drawn once, in its final state.
3. **Switches are scanned every pass**: footswitch latency is bounded by one frame, independent of incoming traffic.
4. **"Changed" means "differs from what's displayed"**, not "differs from the previous state". This makes dedupe generic across message types, and handles `cc_receive` correctly: a press that changes state without repainting still gets drawn on the next frame.

The codebase already has two pieces of this pattern to build on:

- `cc_inc`/`cc_dec` RX already queues repaints in `pending_cc_step_updates` and flushes them once per loop.
- `core/display_model.py` already models the screen as pure data, separate from drawing.

CircuitPython 7 also supports `display.auto_refresh = False` with explicit `display.refresh()`, which fits a fixed render rate. How much that saves on this hardware hasn't been measured yet.

## Consequences

**Positive**:

- Per-message cost drops to state updates (microseconds), so bursts clear quickly without special cases.
- Footswitch response stays bounded during floods.
- One dedupe rule covers notes, CC, PC, select groups, and keytimes. The note-specific dedupe in #206 and the CC-dedupe follow-up become unnecessary.
- The DIN input gets read far more often, so overflow becomes rare. The buffer should still be enlarged (see below).

**Negative**:

- Up to one frame (~33 ms at 30 fps) between a message arriving and the LED or screen changing. That's below what's noticeable for LED feedback, and faster than any backlogged message today.
- A meaningful refactor of `code.py`. Every code path that calls `set_button_state` directly (27 call sites today: presses, RX, flash timers, LED init and page switches, select groups, keytimes, `cc_inc`/`cc_dec`) has to go through the dirty-and-render path instead.
- Needs bench validation against a chatty host (Visibox omni mode) on at least one TFT device and one non-TFT device.

## Interim decisions

These apply until the split lands:

- **Merge #206 as is**: it's a correct step toward this design and fixes the reported problem.
- **No ~10 ms time cap on the drain loop**: it's a stopgap for rendering inside receive, which this design removes.
- **No separate CC dedupe**: covered by decision point 4.
- **Enlarge the DIN receive buffer** (e.g. `receiver_buffer_size=512`, about 160 ms of continuous DIN traffic for 0.5 KB of RAM). Worth doing regardless, in #206 or #207.
- **Per-event console prints only in dev mode** (#207). Incoming MIDI additionally stays behind #206's `MIDI_RX_LOG`.

## Alternatives considered

- **Time-capped drain (~10 ms)**: bounds footswitch latency but keeps repaint cost inside receive. Rejected as the long-term answer; see interim decisions.
- **Per-type dedupe (notes in #206, then CC)**: grows special cases, and the CC version breaks `cc_receive`. Rejected in favor of comparing against what's displayed.
- **Concurrency (threads, `asyncio`, second core)**: not available or not useful on CircuitPython 7.3.1 on the RP2040. `asyncio` is cooperative and wouldn't make repaints cheaper.

## Related decision: MIDI Learn transport (#54)

Learn will stop parsing the `[MIDI RX ...]` console prints, which #206 turns off by default.

- The editor puts the pedal into Learn mode with an explicit command over the serial connection it already uses.
- The pedal replies with one structured line per message, shaped like a partial button config.
- The editor merges that into the form as an unsaved change. The normal save path validates it and writes `config.json`, so the editor stays the only writer of that file.

Having the pedal write `config.json` or a patch file was rejected. CircuitPython can't safely write to its drive while the host has it mounted, and switching the drive's writer requires a reset.
