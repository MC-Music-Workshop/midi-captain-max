# MIDI Captain Custom Firmware — Design Document

**Status:** Shipped — this design became the current firmware.
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a generic, config-driven, bidirectional MIDI firmware for Paint Audio MIDI Captain pedals (6 and 10-switch variants).

**Architecture:** Hybrid approach — start with Helmut's asyncio core, introduce lightweight abstractions (Button, DisplaySlot, Config loader), refactor to fuller architecture as needed.

**Tech Stack:** CircuitPython 7.x on RP2040, YAML config, adafruit_midi, displayio/ST7789

---

## 1. Project Context

### 1.1 Target Hardware

| Device | Switches | LEDs | Encoder | Expression | Display |
|--------|----------|------|---------|------------|---------|
| STD10 | 10 + encoder push | 30 (3×10) | Yes | 2 inputs | 240×240 ST7789 |
| Mini6 | 6 | 18 (3×6) | No | TBD | 240×240 ST7789 |

### 1.2 Reference Implementations

| Firmware | Strengths | Weaknesses |
|----------|-----------|------------|
| **OEM SuperMode** | Keytimes, pages, 3-segment LEDs, HID | No bidirectional MIDI |
| **Helmut Keller** | Bidirectional CC/SysEx, tuner mode, clean asyncio | Hardcoded mappings, STD10-only |
| **PySwitch** | Action/callback architecture, web config | Complex, Kemper-focused |

### 1.3 Design Principles

- **Bidirectional first**: Host is source of truth, device provides instant feedback
- **Config-driven**: YAML for all mappings, no recompilation needed
- **Device-agnostic**: Abstract hardware differences behind device modules
- **Web-tool-ready**: Design config format with future GUI editor in mind
- **YAGNI**: Build only what's needed for MVP, extend later

---

## 2. Feature Priority (MVP → Future)

### MVP (v1.0)

| Priority | Feature | Status |
|----------|---------|--------|
| 1 | Bidirectional CC (host → device LED/display sync) | 🔨 Demo built |
| 2 | Button label slots on screen (per-switch) | Planned |
| 3 | YAML config for button→MIDI mappings | Planned |
| 4 | Momentary + Toggle modes per button | Planned |
| 5 | Multi-device support (STD10 + Mini6) | Abstraction started |

### Post-MVP

| Priority | Feature |
|----------|---------|
| 6 | SysEx for dynamic labels/colors |
| 7 | Long-press detection (secondary actions) |
| 8 | Center status area (preset name, etc.) |
| 9 | Keytimes / multi-press cycling |
| 10 | Pages / banks |
| 11 | State machine / button dependencies |
| 12 | Tuner display (Note + pitch deviation) |
| 13 | Expression pedal support |
| 14 | Encoder support |
| 15 | Web-based config tool |

---

## 3. Architecture

### 3.1 Module Structure

```
firmware/dev/
├── code.py                 # Main entry point
├── config.yaml             # User configuration
├── devices/
│   ├── __init__.py
│   ├── std10.py            # STD10 pin definitions
│   └── mini6.py            # Mini6 pin definitions (planned)
├── core/
│   ├── __init__.py
│   ├── button.py           # Button class (debounce, modes)
│   ├── led.py              # LED controller (per-switch colors)
│   ├── midi_handler.py     # MIDI send/receive logic
│   ├── display.py          # Display layout manager
│   └── config_loader.py    # YAML config parser
└── experiments/
    └── bidirectional_demo.py   # Current experiment
```

### 3.2 Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                         HOST (DAW/Plugin Host)              │
└─────────────────────────────────────────────────────────────┘
                    ↑ CC/PC/SysEx            ↓ CC/PC/SysEx
┌─────────────────────────────────────────────────────────────┐
│                       MIDI Handler                          │
│  - Parse incoming messages                                  │
│  - Route to appropriate handler (LED, Display, State)       │
│  - Queue outgoing messages                                  │
└─────────────────────────────────────────────────────────────┘
        ↑                    ↓                    ↓
┌───────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│  Button Manager│  │  LED Controller │  │  Display Manager    │
│  - Scan inputs │  │  - Update colors│  │  - Render slots     │
│  - Debounce    │  │  - Brightness   │  │  - Update labels    │
│  - Mode logic  │  │  - Per-switch   │  │  - Status area      │
└───────────────┘  └─────────────────┘  └─────────────────────┘
        ↑                    ↑                    ↑
┌─────────────────────────────────────────────────────────────┐
│                     Config (YAML)                           │
│  - Button mappings (CC, PC, Note)                          │
│  - Colors, labels                                          │
│  - Modes (momentary, toggle)                               │
│  - Display layout                                          │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 State Model (Hybrid)

The device maintains local state for instant feedback, but host is authoritative:

```python
class ButtonState:
    local_value: int      # Local toggle state (0 or 127)
    host_value: int       # Last value received from host
    display_value: int    # What's shown (host_value if set, else local_value)
    
    def on_press(self):
        self.local_value = 127 if self.local_value == 0 else 0
        # Send CC to host
        # Update LED immediately (local feedback)
    
    def on_host_update(self, value):
        self.host_value = value
        self.display_value = value  # Host overrides local
        # Update LED to match host
```

---

## 4. Configuration Format

### 4.1 YAML Structure

```yaml
# config.yaml

device: std10  # or mini6

midi:
  channel: 1
  usb: true
  serial: true  # 5-pin DIN

global:
  led_brightness: 0.3
  led_brightness_dim: 0.05

buttons:
  - id: 0
    name: "Encoder"
    cc: 14
    mode: momentary
    color: cyan
    
  - id: 1
    name: "Drive"
    cc: 20
    mode: toggle
    color: red
    color_off: dark_red
    
  - id: 2
    name: "Delay"
    cc: 21
    mode: toggle
    color: blue
    
  # ... etc

display:
  layout: slots  # or custom
  show_center: true
  center_default: "Ready"
```

### 4.2 Color Palette

Use Helmut's 27-color palette as base, referenced by name:

```yaml
colors:
  black: [0, 0, 0]
  red: [255, 0, 0]
  dark_red: [128, 0, 0]
  green: [0, 255, 0]
  blue: [0, 0, 255]
  cyan: [0, 255, 255]
  yellow: [255, 255, 0]
  orange: [255, 128, 0]
  # ... etc (full palette in code)
```

---

## 5. Display Layout

### 5.1 STD10 Layout (MVP)

```
┌─────────────────────────────────────┐
│  [Sw1]  [Sw2]  [Sw3]  [Sw4]  [Up]  │  ← 5 slots, 48px each
├─────────────────────────────────────┤
│                                     │
│           Center Status             │  ← Preset name, mode, etc
│                                     │
├─────────────────────────────────────┤
│  [SwA]  [SwB]  [SwC]  [SwD]  [Dn]  │  ← 5 slots, 48px each
└─────────────────────────────────────┘
```

### 5.2 Display Slot Properties

```python
class DisplaySlot:
    x: int
    y: int
    width: int
    height: int
    label: str
    color: tuple
    value: int  # 0-127, shown as bar or percentage
    visible: bool
```

### 5.3 Mini6 Layout

```
┌─────────────────────────────────────┐
│    [Sw1]      [Sw2]      [Sw3]     │  ← 3 slots
├─────────────────────────────────────┤
│           Center Status             │
├─────────────────────────────────────┤
│    [SwA]      [SwB]      [SwC]     │  ← 3 slots
└─────────────────────────────────────┘
```

---

## 6. MIDI Protocol

### 6.1 Outgoing (Device → Host)

| Event | Message |
|-------|---------|
| Switch press | CC [mapped_cc] value 127 |
| Switch release | CC [mapped_cc] value 0 |
| Encoder turn | CC [encoder_cc] value (0-127, relative or absolute) |
| Expression pedal | CC [exp_cc] value (0-127) |

### 6.2 Incoming (Host → Device)

| Message | Action |
|---------|--------|
| CC [any mapped] | Update LED state (>63 = on), update display slot value |
| SysEx [0x59, cc, color, label...] | Update button color and label (Helmut format) |
| Note On/Off | Tuner mode: show note name |
| Pitch Bend | Tuner mode: show pitch deviation |

### 6.3 SysEx Format (Helmut-compatible)

```
F0 59 <cc> <color_index> <ascii_label...> F7
```

Example: Set CC20 to red with label "Drive"
```
F0 59 14 08 44 72 69 76 65 F7
     │  │  └─ "Drive" in ASCII
     │  └─ Color index 8 = red
     └─ CC 20 (0x14)
```

---

## 7. Implementation Plan

### Phase 1: Prove Concepts (Current)
- [x] Create bidirectional_demo.py
- [ ] Test on STD10 hardware
- [ ] Verify CC send/receive works

### Phase 2: Display Layout
- [ ] Create display.py module
- [ ] Implement 5+5 slot layout for STD10
- [ ] Show button labels from config
- [ ] Update slot appearance on CC receive

### Phase 3: YAML Config
- [ ] Create config_loader.py
- [ ] Define config.yaml schema
- [ ] Load button mappings at startup
- [ ] Apply colors/labels from config

### Phase 4: Button Modes
- [ ] Create button.py with mode support
- [ ] Implement momentary mode
- [ ] Implement toggle mode
- [ ] Add long-press detection

### Phase 5: Integration
- [ ] Merge experiments into main code.py
- [ ] Full asyncio task structure
- [ ] Add Mini6 device support
- [ ] Test both devices

### Phase 6: Polish
- [ ] SysEx label/color updates
- [ ] Center status area
- [ ] Serial MIDI (5-pin DIN)
- [ ] Expression pedal support
- [ ] Encoder support

---

## 8. Testing Strategy

### 8.1 On-Device Testing
- Deploy to CIRCUITPY, observe via serial console
- Use MIDI monitor to verify outgoing messages
- Use DAW/host to send incoming CC and verify LED response

### 8.2 Host-Side Test Script
Create a simple Python script using `mido` to:
- Send CC messages to device
- Receive CC messages from device
- Verify round-trip timing

### 8.3 Future: Desktop Unit Tests
- Use `blinka` to mock CircuitPython hardware
- Test config parsing
- Test button state logic
- Test display layout calculations

---

## 9. Open Questions

1. **Config hot-reload?** — Should changes to config.yaml take effect without reboot?
2. **Multiple MIDI channels?** — Per-button channel override?
3. **PC message handling?** — How should Program Change affect display?
4. **Bank/page switching?** — How to switch config pages at runtime?
5. **Mini6 expression/encoder?** — Need hardware probing to confirm availability

---

## 10. References

| Resource | Location |
|----------|----------|
| OEM SuperMode docs | `docs/FW-SuperMode-4.0-BriefGuide.txt` |
| Helmut's firmware | `firmware/original_helmut/code.py` |
| Helmut's documentation | `docs/a midi foot controller...pdf` |
| Helmut's GP script | `docs/GLOBAL RACKSPACE Script...gpscript` |
| PySwitch repo | https://github.com/Tunetown/PySwitch |
| Hardware findings | `docs/midicaptain_reverse_engineering_handoff.md` |
| Device abstraction | `firmware/dev/devices/std10.py` |

---

*Document created: 2026-01-23*
*Author: Max Cascone / GitHub Copilot*
