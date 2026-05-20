# MIDI Captain MAX vs. Factory OEM Firmware

A feature-by-feature comparison of **MIDI Captain MAX (MCM)** against **Paint Audio's factory SuperMode 4.0 firmware**, running on the same hardware.

---

## At a Glance

| | **MIDI Captain MAX** | **OEM (Paint Audio SuperMode 4.0)** |
|---|---|---|
| **Bidirectional MIDI** | ✅ Host updates LEDs and display in real time | ❌ One-way only |
| **Config format** | ✅ JSON, schema-validated | ⚠️ Bracketed ASCII (`[1][CC][69][0]`) in `pageX.txt` |
| **Editor** | ✅ GUI Config Editor with live validation | ❌ Hand-edit text files |
| **Firmware updates** | ✅ One-click from the editor | ❌ Manual drag-and-drop |
| **Source** | ✅ Open, CircuitPython | ❌ Closed binary |
| **Custom USB drive name** | ✅ Per-device | ❌ Always `MIDICAPTAIN` |
| **Signed installers** | ✅ macOS + Windows | ❌ N/A |

---

## Feature-by-Feature Parity

### Button Behavior

| OEM Feature | MCM Equivalent | Status |
|---|---|---|
| Multi-press cycling (`keytimes`, up to 9 states) | `mode: "keytimes"` with up to **99** states per button | ✅ Parity (and then some) |
| Short / long press timings (`short_dw`, `short_up`, `long`, `long_up`) | Short + long press via keytimes with independent per-timing cycles | ⚠️ Partial — MCM splits short vs. long, but not separate up/down phases |
| Multiple commands per press (combine PC + CC + NT + HID in one trigger) | One message per state | ❌ Gap — MCM fires one message per state |
| `ledmode: normal` | Default keytimes / toggle behavior | ✅ |
| `ledmode: select` (radio-group exclusivity) | `mode: "select"` with `select_group` + `select_repress` (`resend` / `nothing` / `deselect`) | ✅ Parity, more configurable |
| `ledmode: tap` (beat flash) | — | ❌ Gap |
| Per-LED-segment color (3 segments per ring) | Single color per button (all 3 segments lit same color) | ❌ Gap — MCM treats the ring as one color |
| Momentary behavior | `mode: "momentary"` | ✅ |
| Toggle behavior | `mode: "toggle"` | ✅ |
| — | `mode: "flash"` (brief LED flash for PC types) | 🆕 MCM-only |

### Message Types

| OEM Feature | MCM Equivalent | Status |
|---|---|---|
| MIDI CC (`[ch][CC][num][val]`) | `type: "cc"` with `cc`, `cc_on`, `cc_off`, `channel` | ✅ |
| MIDI Note (`[ch][NT][note][vel]`) | `type: "note"` | ✅ |
| MIDI PC (`[ch][PC][num][-]`) | `type: "pc"` | ✅ |
| PC increment (`[1][PC][inc1..inc5][-]`) | `type: "pc_inc"` with configurable `pc_step` | ✅ Parity (any step, not just 1–5) |
| PC decrement (`[1][PC][dec1..dec5][-]`) | `type: "pc_dec"` with `pc_step` | ✅ |
| PC random (`[2][PC][random][-]`) | — | ❌ Gap |
| PC auto-bank (`[1][PC][auto][bank_inc / bank_dec / 0..7]`) | — | ❌ Gap |
| HID keyboard / mouse | `type: "hid"` | ✅ |
| HID `send` / `press` / `release` / modifiers | Supported via CircuitPython HID layer | ✅ |
| HID `delay` (pure delay command) | — | ❌ Gap (no scripted delay primitive) |

### Pages

| OEM Feature | MCM Equivalent | Status |
|---|---|---|
| Multiple pages (`pageX.txt`, up to 99), long-press right key to switch | — | ❌ Gap — pages not implemented yet, on the backlog |
| `page_name` | — | ❌ Gap |
| External page jump via incoming `CC 20 XX` | — | ❌ Gap (depends on pages landing first) |
| PC + page persistence every 30 s | — | ❌ Gap |

### Expression Pedals

| OEM Feature | MCM Equivalent | Status |
|---|---|---|
| Two expression pedals (`exp1_CH`, `exp1_CC`, `exp2_CH`, `exp2_CC`) | Full per-pedal config: `cc`, `channel`, `min`, `max`, `polarity`, `threshold`, `label` | ✅ Parity, richer config |
| Live value display on device | ✅ MCM shows pedal value on the OLED | ✅ |
| Hardware availability | STD10 only (the only Captain with pedal ports) | Same on both |

### Encoder

| OEM Feature | MCM Equivalent | Status |
|---|---|---|
| `encoder_CC`, `encoder_NAME` | Full encoder config: `cc`, `label`, `min`, `max`, `initial`, `steps`, `channel` | ✅ Parity, richer config |
| Encoder push button | First-class `encoder.push` block: `cc`, `mode`, `cc_on`, `cc_off`, `label`, `channel` | 🆕 MCM-only level of control |

### Global / Display Settings

| OEM Feature | MCM Equivalent | Status |
|---|---|---|
| `midithrough = on/off` | — | ❌ Gap — no MIDI passthrough setting |
| `display_number_ABC` (123 / abc3 / abc4 / abc5 / abc8 grouping) | — | ❌ Gap — MCM doesn't ship the PC-display grouping modes |
| `group_number`, `display_pc_offset`, `display_bank_offset` | — | ❌ Gap (tied to pages / PC display) |
| — | Per-zone text-size config (`button_text_size`, `status_text_size`, `expression_text_size`) | 🆕 MCM-only |
| — | Custom USB drive name (`usb_drive_name`) | 🆕 MCM-only |
| — | Bidirectional MIDI (host can drive LEDs / display) | 🆕 MCM-only headline feature |

### Tooling & Workflow

| OEM | MCM | Status |
|---|---|---|
| Hand-edit `supersetup/pageX.txt` in a text editor | GUI Config Editor: visual layout, color picker, live validation, device auto-detect | 🆕 MCM-only |
| No schema / validation | Published `config.schema.json` | 🆕 MCM-only |
| Manual firmware flashing (drag-and-drop, hold KEY0 on boot) | One-click firmware install from the GUI | 🆕 MCM-only |
| No dev iteration loop | **Dev Mode** — iterate without remounting | 🆕 MCM-only |
| Closed binary firmware | Open-source CircuitPython | 🆕 MCM-only |
| No signed installers | Signed `.dmg` (macOS), code-signed `.exe`/`.msi` (Windows) | 🆕 MCM-only |

### Supported Hardware

| Device | MCM | OEM |
|---|---|---|
| STD10 | ✅ | ✅ |
| MINI6 | ✅ | ✅ |
| NANO4 | ✅ | ✅ |
| DUO   | ✅ | ✅ |
| ONE   | ✅ | ✅ |

Paint Audio's newer **EXP/SW** is a separate product, not a Captain variant; MCM has not been ported to it.

---

## Summary

**Where MCM clearly wins:**
- Bidirectional MIDI — the entire reason this firmware exists
- GUI editor, schema-validated JSON, signed installers, one-click updates
- Custom USB drive names, dev mode, open source
- `select` radio-group mode, `flash` mode, configurable `pc_step`, richer encoder + expression pedal config

**Where OEM still has features MCM lacks:**
- Pages and everything tied to them (page names, CC 20 page jump, PC/page persistence)
- `tap` LED mode (beat flash)
- Multiple commands chained on a single trigger
- Separate `short_up` / `long_up` timing phases (MCM has short vs. long, but not up/down per timing)
- Per-LED-segment colors on the 3-segment LED ring
- PC `random` and PC `auto` bank macros
- HID `delay` primitive
- MIDI passthrough toggle
- PC display grouping modes (`abc3` / `abc4` / etc.)

Several of these are on the [public backlog](https://github.com/MC-Music-Workshop/midi-captain-max/issues); pages are the biggest tracked item.

---

## The Pitch

MCM keeps the parts of OEM SuperMode that real players use — keytimes cycling, expression pedals, HID, all the MIDI types — and adds the things performers have been asking for: bidirectional state, a real editor, validated config, painless updates, and open source under the hood. The OEM still wins on a handful of advanced macros and on pages, both of which are on the roadmap.

Built on Paint Audio's solid hardware. Extended by an open-source community.

---

*Questions? [Open an issue](https://github.com/MC-Music-Workshop/midi-captain-max/issues). MCM is free to use for personal and commercial performance — see [LICENSE](../../LICENSE).*
