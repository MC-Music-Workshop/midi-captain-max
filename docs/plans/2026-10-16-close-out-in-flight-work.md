# Plan: close out in-flight work

- **Date**: 2026-10-16
- **Status**: In progress. Phases 0–4 done (2026-10-18); next is Phase 5, #54 Learn
- **Related**: [ADR 0001](../adr/0001-separate-midi-receive-from-rendering.md), #202, #206, #200, #207, #54, #208, #190

## Goal

Land every open branch on `main` in an order that keeps conflicts small, keeps each firmware change bench-testable on its own, and groups hardware testing into a few sessions.

## In-flight work

| Work | Branch / worktree | Kind | State |
|---|---|---|---|
| #202 saved configs (#36) | `36-saved-configs` | Editor | Merged (`0286585`) |
| #206 MIDI RX throughput (jjeff) | `fix/midi-rx-throughput` | Firmware | Merged (`804b48e`) |
| #200 keytimes listen CC | `200-keytimes-listen-cc` | Firmware | Merged via #210 (`b8d20dd`); editor fields follow-up #211 |
| #207 per-event prints in dev mode only | none | Firmware | Deferred (see Phase 4); DIN buffer shipped separately in #212 |
| #54 MIDI Learn | `54-learn-design` | Editor + firmware | Design doc + first attempt ported onto current `main` (old branch archived as `archive/54-midi-learn`), no PR |
| #208 receive/render split (ADR 0001) | none yet | Firmware | ADR committed, issue filed |
| #190 device rename | `190-device-rename` | Editor + firmware | Plan only |
| Unique volume ID | none yet (`device-ambiguity` session) | Editor | Design only |

## Decisions this plan is built on

- **#206 merges as is**: no ~10 ms time cap on the drain loop, no separate CC-dedupe follow-up. ADR 0001 replaces both.
- **#206 doesn't block on Learn**: Learn stops reading the `[MIDI RX ...]` console prints entirely.
- **#54 is reworked, not patched**: the editor sends an explicit start-learn command over the serial connection it already uses; the pedal replies with one structured line per message, shaped like a partial button config; the editor merges it into the form as an unsaved change and the normal save path validates and writes `config.json`. The pedal never writes files.
- **#207**: per-event prints (MIDI in/out, encoder, expression, page, HID) only print in dev mode, written as `if DEV_MODE: print(...)` at each site. Startup summary, `[CONFIG WARN]` and errors stay on. #206's `MIDI_RX_LOG` stays off even in dev mode.
- **DIN receive buffer**: raise `receiver_buffer_size` from 64 to 512 bytes, shipped with #207.
- **Receive/render split (ADR 0001)**: lands after the other firmware branches, so it doesn't keep conflicting with them and converts every redraw path in one pass.

## Phases

### Phase 0: cleanup and paperwork (no risk)

- [x] Commit `docs/adr/0001-separate-midi-receive-from-rendering.md` and this plan to `main`
- [x] File the receive/render split implementation issue (#208); add it to the ADR's **Related** line
- [x] Delete merged local branches: `off-color`, `midi-thru-chan`, `fix/save-restart-serial-park`, `faceplate-store`
- [x] Delete the empty `118-incoming-led-control` branch. #118 stays open: #197 added a separate listen CC and off colors, not the runtime color and blink control #118 asks for.
- [x] Delete the stale `.worktrees/15-pages` and `.worktrees/15-pages-p4d` folders (only Vite cache files aren't already in git), then `git worktree prune`
- [x] `OEM` stash: its 552 untracked Paint Audio files (FW 3.5 and 5.0 packages, manuals, wallpapers, partnership one-pager) exported to `~/Documents/PaintAudio_OEM`, then dropped
- [x] Old branches decided: keep `hot-reload-plan`; archive `marketing` and `ui-test-plan` (tags `archive/marketing`, `archive/ui-test-plan`, pushed); delete `wokwi-emulator-spike`. The `ui-test-plan` doc's recommended approach was already built in `config-editor/e2e/`, but nothing runs it automatically: filed #209.
- [x] Delete the `marketing`, `ui-test-plan` and `wokwi-emulator-spike` branches, locally and on `origin`
- [x] Archive session files for merged work (moved to `~/.claude/session-archive/`)

### Phase 1: #202 saved configs (editor)

- [x] Smoke test on the bench
- [x] Merge

### Phase 2: #206 MIDI RX throughput (firmware)

- [x] CI: fork PRs get no CI (`ci.yml` triggers on push only), so the head commit was pushed to a temporary `ci/pr-206` branch. All jobs passed except macOS notarization, which fails on `main` too (see **Found along the way**).
- [x] Bench test on a NANO4 with `tools/visibox-flood.sh` standing in for Visibox omni mode. v1.14.0 fell behind at the first clip start and never caught up; #206 followed every clip change with no flicker over USB and DIN, and 45 footswitch presses during the flood all registered immediately.
- [x] Reply to jjeff: thanks, merging as is, link ADR 0001 as the longer-term direction
- [x] Merge

### Phase 3: #200 keytimes listen CC (firmware)

- [x] Rebase onto `main`; resolve `midi_rx.py` by keeping the 3-item return and adding `find_note_rx_target`
- [x] Run the full `./tools/test-all.sh`, including `cargo`
- [x] Bench test (found and fixed a press after a host change resending the host's entry)
- [x] Add the `firmware/AGENTS.md` note
- [x] File a follow-up issue for the editor UI (new fields are JSON-only for now): #211
- [x] Push, open the PR, merge: #210

### Phase 4: DIN buffer + bench suite (firmware); #207 deferred

Rescoped 2026-10-17: the suspected serial stall didn't reproduce on macOS, so print gating (#207) is deferred (findings on the issue). Only the DIN buffer shipped.

- [x] Bench check for the stall (macOS, console held open but unread, `[PAGE]` prints from paced CC page flips): no stall. macOS buffers about 44.9 KB of unread output, then drops the rest; the pedal kept switching pages and a footswitch press still worked. Linux and Windows untested.
- [x] Raise `receiver_buffer_size` to 512: #212. A 100-message DIN burst lost about half at 64 bytes (52/53/52) and arrives complete at 512 (100/100).
- [x] Hardware bench suite as a release step (`tools/bench/`, `docs/bench-tests.md`): #213
- [ ] ~~Gate per-event prints behind dev mode~~ deferred (#207)

### Phase 5: #54 MIDI Learn rework (editor + firmware)

**Spike (2026-10-18, NANO4, throwaway branch `54-learn-spike`)**: a command channel over the serial console works on CircuitPython 7.3.1 with no `boot.py` change.
- Read with `usb_cdc.console.in_waiting` and one `read(n)`. `supervisor.runtime.serial_bytes_available` is only a bool on CP 7, and `sys.stdin.read(1)` costs ~1 ms per byte (a 64-byte pass blocked the loop ~54 ms).
- Measured: `PING` round trip ~8 ms median; idle loop ~410 passes/s; 4 KB of junk handled in 284 ms; `[LEARN] {json}` replies correct for CC, note and PC over USB and DIN.
- Each reply line costs ~4 ms to print. The host must finish every write (non-blocking serial writes can be partial) and never send Ctrl-C/Ctrl-D except to restart the pedal.

**Proposed rule: learning is one-shot.** `LEARN` → `[LEARN] on`; the pedal reports the first CC, note-on (velocity > 0) or PC from USB or DIN as one `[LEARN] {json}` line, then turns learning off and prints `[LEARN] off`. Note-offs, clock, SysEx and pitch bend are skipped. `LEARN STOP` cancels; the editor gives up after 30 s. The editor fills only the message identity (type, channel, number), as `midiLearn.ts` already does.

**Pre-mortem (likely user reports) and how the design answers them:**
1. Learn times out with no reason on older firmware: if `[LEARN] on` doesn't arrive within ~1 s, say the firmware doesn't support Learn.
2. Learned the wrong CC because host feedback for other buttons arrived first: one-shot makes retrying cheap, the result shows as an unsaved change, and the docs say to pause host feedback while learning.
3. A learned button stops following `global_channel`: leave `channel` out when it equals the global channel.
4. Learning a page-control CC switches the page, or another button reacts. **Decided (Max, 2026-10-18): only report it.** The captured message goes to the editor and the pedal otherwise ignores it (no page switch, no LED change).
5. "Sent program 5, learned 4": hosts count programs 1–128, the config 0–127. Show them consistently with the rest of the editor.
6. Learn wrote the sending CC, but the user wanted the listening one (`cc_receive`). **Decided (Max, 2026-10-18): two Learn actions.** "Learn send" sets type, channel and number; "Learn listen" writes `cc_receive`. Design doc to settle where Learn listen is offered (`cc_receive` is CC-only) and what it does when a non-CC message arrives.
7. Learn on keytimes or CC+/CC- buttons does nothing useful (no single type/number): hide or disable Learn on those modes for now.
8. With two pedals connected, Learn opened the wrong pedal's console (same USB name; same volume ID until Phase 8): check how the editor maps a drive to its serial port; note the Phase 8 dependency.
9. "Port busy" when another program holds the console or Save & Restart runs during learning: clear errors, and end learning automatically before Save.
10. Rarer: 14-bit/NRPN controllers learn CC 99; a crashed `code.py` sits at the REPL. Both acceptable with a clear timeout message.

- [x] Spike: serial command channel on CP 7.3.1
- [x] Decide pre-mortem 4 and 6
- [x] Design doc: `docs/plans/2026-10-21-issue-54-midi-learn-design.md` (protocol, capture rule, Save & Restart interplay, tests incl. an automated learn check in `tools/bench/`), answering the pre-mortem
- [x] Bring the first attempt up to `main`: ported onto `54-learn-design` (`58bd453`), kept both sides of the `lib.rs`, `api.ts`, `ButtonRow.svelte` and `config-editor/AGENTS.md` conflicts; old branch archived as `archive/54-midi-learn`
- [ ] Replace console-print scraping with the command-and-reply protocol (keep `midiLearn.ts` form mapping and the `learn_midi` / `cancel_midi_learn` command shape; rewrite the serial reader; add the firmware learn handler)
- [ ] Update `docs/user/midi-learn.md`
- [ ] Bench test over USB and DIN
- [ ] Open the PR, merge

**Release point**: cut a firmware release here (#206, #200, #212, Learn). Run `tools/bench/run.sh` first and paste its table into the release notes.

### Phase 6: #208 receive/render split (firmware, ADR 0001)

- [ ] Implement per the ADR: receive updates state and marks buttons dirty; render compares against what's displayed at ~30 fps; switches scanned every pass
- [ ] Route all direct `set_button_state` call sites through the render path; remove #206's note-only dedupe
- [ ] Bench test with Visibox on one TFT device and one non-TFT device
- [ ] Merge; ship in its own release

### Phases 7–8: #190 device rename, then unique volume ID (independent of firmware track)

- [ ] #190: plan posted on the issue (2026-10-30; stale worktree removed), start a fresh branch from `main`; hardware check whether `boot.py` can set the drive label on CircuitPython 7.3.1; implement per plan
- [ ] Unique volume ID: answer the UX question (auto banner + Fix button, plus a manual per-drive button); then design doc, plan, implementation. Starts after #190, since both touch device detection in `device.rs` and the device picker.

### Phase 9: config schema housekeeping

Originally scheduled after everything above; the user pulled it forward on 2026-10-18 and all three landed together in PR #217.

- [x] #215: editor saves silently drop fields the Rust structs don't model. Today that deletes keytimes host-sync settings (`short_cc_receive`, `long_cc_receive`, `rx_value`) on **Save to Device** / **Save to File**. Fix: write the JSON the editor sent instead of re-serializing the struct, and add the missing Rust fields with validation.
- [x] #216: a Rust test that builds a config setting every schema property and fails if any key is lost in a round trip, so schema/Rust drift fails CI.
- [x] #211: editor fields for keytimes host sync (Listen CC per cycle, Receive value per entry, duplicate-value hint), plus the Keytimes user guide.

`v1.15.0-alpha.1` predates #217: in that build, saving from the editor removes host-sync settings. Releases from #217 on are fine.

## Bench sessions

1. ~~#202 smoke test, #206 flood test (USB and DIN)~~ done; #190 drive-label check still open
2. ~~#200, DIN buffer, serial stall check~~ done; Learn over USB and DIN still to do
3. Receive/render split, flood test on a TFT and a non-TFT device

Flood tests use `tools/visibox-flood.sh "<port>" [seconds] [clip_secs]` (needs `sendmidi`). Automated checks: `tools/bench/run.sh` (see `docs/bench-tests.md`). The NANO4 is on `main` firmware with the `tools/bench/configs/nano4-207-serial-din-test.json` config; its original config is in `~/Documents/MIDICaptainMAX/configs/nano4-before-206-test.json`.

## Found along the way

- **macOS notarization fails in CI** (`HTTP 401 Invalid credentials`) on `main` and every branch since 2026-10-17, which also blocked the `v1.15.0-alpha.1` release. The org secret `APPLE_APP_PASSWORD` was regenerated on 2026-10-17, but runs after that still get 401: check `APPLE_APP_PASSWORD` (exact paste), `APPLE_ID`, `APPLE_TEAM_ID`, and the repo's access to the org secrets.
- **Fork PRs get no CI**: `ci.yml` has no `pull_request` trigger. Consider adding one (or a maintainer-run workflow) before the next outside contribution.
- **Editor e2e specs run nowhere automatically**: #209.
- **Editor save drops unmodeled fields**: #215, #216, fixed in PR #217 (Phase 9).

## Open decisions (owner: Max)

- Unique volume ID UX
- Whether to file the fork-PR CI gap as an issue
