# MIDI Captain MAX vs. Factory OEM Firmware

**Same hardware. Smarter brain.**
A side-by-side look at what changes when you flash MIDI Captain MAX (MCM) onto your Paint Audio MIDI Captain.

---

## The Short Version

| | **MIDI Captain MAX** | **OEM (Paint Audio SuperMode)** |
|---|---|---|
| **Bidirectional MIDI** | ✅ Host controls LEDs and display in real time | ❌ One-way only — buttons send, device never listens |
| **Configuration** | ✅ Visual GUI Config Editor with live validation | ❌ Hand-edit `pageX.txt` files in a text editor |
| **Firmware updates** | ✅ One click in the Config Editor | ❌ Manual drag-and-drop, hold-button-on-boot ritual |
| **Format** | ✅ Modern, schema-validated JSON | ⚠️ Bracketed `[1][CC][69][0]` ASCII strings |
| **Recovery if it breaks** | ✅ Re-mount, restore backup, done | ⚠️ Same — but more chances to break it by hand |
| **Multi-device support** | ✅ Per-device custom USB drive names | ❌ Every device mounts as `MIDICAPTAIN` |
| **Source code** | ✅ Open, CircuitPython, hackable | ❌ Closed, opaque binary |
| **Stage-ready stability** | ✅ Tested, signed installers, no surprises | ⚠️ Functional, but no public test suite |

---

## What MCM Adds

### Bidirectional MIDI — the headline feature
Your DAW, plugin host, or backing-track rig can **talk back to the pedalboard**. LEDs light up when a plugin bypass toggles. Button colors reflect actual plugin state, not just the last thing you pressed. This is what the OEM firmware fundamentally can't do.

- **Gig Performer / MainStage** — button LEDs sync to plugin bypass
- **Ableton Live** — visual feedback on track mutes and solos
- **Helix Native / Guitar Rig** — effect-on confirmation, not guesswork

### A real config editor
No more editing `page0.txt` and counting square brackets. The GUI Config Editor gives you:

- **Visual button layout** matching your device
- **Real-time validation** — errors caught before you save
- **Color picker** — pick LED colors visually, not by hex
- **Auto device detection** — plug in and it knows
- **One-click firmware install** — no `deploy.sh`, no boot-button ritual

### Modern config format
MCM uses **JSON** with a published schema. Diff-friendly, version-controllable, copy-pasteable between devices. The OEM uses bracketed strings like `short_dw1 = [1][CC][69][0]` — functional, but a chore to read and impossible to validate without running it.

### Short / Long press (Keytimes mode)
Each button fires different messages on short tap vs. long hold, with **independent multi-state cycles** per timing class. The OEM has `short_dw / short_up / long / long_up` timings too — but MCM keeps them readable, GUI-editable, and schema-validated, and the cycles are wired into the LED render so state and color stay in sync.

### HID — keyboard and mouse, not just MIDI
Both firmwares can send HID. MCM exposes it as a first-class option in the GUI: any button can send keystrokes or mouse clicks to control **any** application, not just MIDI hosts.

### Custom USB drive names
Got two Captains? Three? Name them. `STAGE_LEFT`, `STAGE_RIGHT`, `STUDIO`. They persist across power cycles. The OEM mounts every device as `MIDICAPTAIN`, which is fine until you plug two in at once.

### Dev Mode
Iterate on config without remounting the device every time. Designed for the way real users actually tweak setups — repeatedly, while testing.

### Signed installers
Signed `.dmg` for macOS, code-signed `.exe` / `.msi` for Windows. No "unidentified developer" warnings, no right-click-to-open ritual, no SmartScreen scaring your bandmate.

### Open source
MCM is **CircuitPython** — readable, hackable, forkable. Want a custom behavior? Edit `code.py`. The OEM is a closed binary; what you get is what you get.

---

## Where MCM Is Still Catching Up

- **EXP/SW device** — Paint Audio's newer EXP/SW unit is a separate product from the Captain series. MCM has not been ported to it; reverse-engineering is on hold pending demand.
- **PC `random` and bank macros** — OEM has a few built-in program-change conveniences (`[2][PC][random][-]`, `[1][PC][auto][bank_inc]`) that MCM doesn't expose yet. MCM **does** ship `pc_inc` / `pc_dec` for stepping program changes.
- **`tap` LED mode** — OEM has a beat-flash LED effect for tap-tempo buttons.

> **Note on expression pedals:** MCM fully supports expression pedals on the **STD10** (the only Captain with expression-pedal ports), including live value display on the device screen.

These are on the roadmap — see the [open issues](https://github.com/MC-Music-Workshop/midi-captain-max/issues) and the [project board](https://github.com/orgs/MC-Music-Workshop/projects/1/views/1).

---

## Supported Devices

| Device | MCM | OEM |
|---|---|---|
| STD10 | ✅ | ✅ |
| MINI6 | ✅ | ✅ |
| NANO4 | ✅ | ✅ |
| DUO   | ✅ | ✅ |
| ONE   | ✅ | ✅ |

Paint Audio's newer **EXP/SW** is a separate product, not a Captain variant; MCM has not been ported to it.

---

## Risk & Reversibility

MCM is **fully reversible**. Back up your OEM `supersetup/` folder before installing, and you can flip back any time by mounting the device, erasing it, and copying the backup back. The Config Editor's first-run flow guides you through this.

If something goes wrong mid-install, the device still mounts as a USB drive — recovery is always a drag-and-drop away.

---

## The Bottom Line

**OEM firmware** turns the MIDI Captain into a perfectly capable one-way MIDI controller, if you're comfortable hand-editing config files and don't need your pedalboard to know what your software is doing.

**MIDI Captain MAX** turns it into a **stage-ready bidirectional controller** with a real GUI, real validation, real updates, and the freedom that comes with open source — without giving up any of the hardware you already own.

Built on Paint Audio's solid hardware. Extended by an open-source community.

---

*Questions? [Open an issue](https://github.com/MC-Music-Workshop/midi-captain-max/issues). MCM is free to use for personal and commercial performance — see [LICENSE](../../LICENSE).*
