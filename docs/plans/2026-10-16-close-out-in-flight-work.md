# Plan: close out in-flight work

- **Date**: 2026-10-16
- **Status**: In progress. Phases 0–2 done (2026-10-17); next is Phase 3, rebasing #200 onto `main`
- **Related**: [ADR 0001](../adr/0001-separate-midi-receive-from-rendering.md), #202, #206, #200, #207, #54, #208, #190

## Goal

Land every open branch on `main` in an order that keeps conflicts small, keeps each firmware change bench-testable on its own, and groups hardware testing into a few sessions.

## In-flight work

| Work | Branch / worktree | Kind | State |
|---|---|---|---|
| #202 saved configs (#36) | `36-saved-configs` | Editor | Merged (`0286585`) |
| #206 MIDI RX throughput (jjeff) | `fix/midi-rx-throughput` | Firmware | Merged (`804b48e`) |
| #200 keytimes listen CC | `200-keytimes-listen-cc` | Firmware | 3 commits, latest (`d3db6dd`) unpushed, no PR, `cargo test` never run |
| #207 per-event prints in dev mode only | none yet | Firmware | Issue filed |
| #54 MIDI Learn | `54-midi-learn` | Editor + firmware | 1 commit (log-scraping design, now superseded), no PR |
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

- [ ] Rebase onto `main`; resolve `midi_rx.py` by keeping the 3-item return and adding `find_note_rx_target`
- [ ] Run the full `./tools/test-all.sh`, including `cargo`
- [ ] Bench test
- [ ] Add the `firmware/AGENTS.md` note
- [ ] File a follow-up issue for the editor UI (new fields are JSON-only for now)
- [ ] Push, open the PR, merge

### Phase 4: #207 quiet serial + DIN buffer (firmware)

- [ ] Gate per-event prints behind dev mode
- [ ] Raise `receiver_buffer_size` to 512
- [ ] Bench check: open a serial terminal, suspend it with Ctrl-Z, and confirm footswitches and LEDs still respond
- [ ] Open the PR, merge

Lands after #206 and #200 because it touches many lines in `code.py`.

### Phase 5: #54 MIDI Learn rework (editor + firmware)

- [ ] Rebase onto `main` (now with #202); keep both sides of the `lib.rs`, `api.ts` and `config-editor/AGENTS.md` conflicts
- [ ] Replace console-print scraping with the command-and-reply protocol (keep `midiLearn.ts` form mapping and the `learn_midi` / `cancel_midi_learn` command shape; rewrite the serial reader; add the firmware learn handler)
- [ ] Update `docs/user/midi-learn.md`
- [ ] Bench test over USB and DIN
- [ ] Open the PR, merge

**Release point**: cut a firmware release here (#206, #200, #207, Learn).

### Phase 6: #208 receive/render split (firmware, ADR 0001)

- [ ] Implement per the ADR: receive updates state and marks buttons dirty; render compares against what's displayed at ~30 fps; switches scanned every pass
- [ ] Route all direct `set_button_state` call sites through the render path; remove #206's note-only dedupe
- [ ] Bench test with Visibox on one TFT device and one non-TFT device
- [ ] Merge; ship in its own release

### Phases 7–8: #190 device rename, then unique volume ID (independent of firmware track)

- [ ] #190: bring the worktree up to `main`; hardware check whether `boot.py` can set the drive label on CircuitPython 7.3.1; implement per plan
- [ ] Unique volume ID: answer the UX question (auto banner + Fix button, plus a manual per-drive button); then design doc, plan, implementation. Starts after #190, since both touch device detection in `device.rs` and the device picker.

## Bench sessions

1. ~~#202 smoke test, #206 flood test (USB and DIN)~~ done; #190 drive-label check still open
2. #200, #207 suspended-terminal check, Learn over USB and DIN
3. Receive/render split, flood test on a TFT and a non-TFT device

Flood tests use `tools/visibox-flood.sh "<port>" [seconds] [clip_secs]` (needs `sendmidi`). The NANO4 is on #206 firmware with buttons set to notes 60–63; its original config is in `~/Documents/MIDICaptainMAX/configs/nano4-before-206-test.json`.

## Found along the way

- **macOS notarization fails in CI** (`HTTP 401 Invalid credentials`) on `main` and every branch since 2026-10-17. The Apple app-specific password in the repo secrets needs regenerating (see `.github/AGENTS.md`).
- **Fork PRs get no CI**: `ci.yml` has no `pull_request` trigger. Consider adding one (or a maintainer-run workflow) before the next outside contribution.
- **Editor e2e specs run nowhere automatically**: #209.

## Open decisions (owner: Max)

- Unique volume ID UX
- Whether to file the fork-PR CI gap as an issue
