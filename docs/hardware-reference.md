# MIDI Captain Hardware Reference

> **Last Updated:** April 3, 2026
> **Verified On:** STD10, Mini6, NANO4, DUO2, and ONE hardware with CircuitPython 7.3.1

This document contains verified hardware specifications for Paint Audio MIDI Captain devices.
For historical context on how these were discovered, see [midicaptain_reverse_engineering_handoff.md](midicaptain_reverse_engineering_handoff.md).

---

## Device Auto-Detection

The firmware automatically detects which device it's running on by probing hardware pins at startup:

- **STD10**: Has encoder on GP2/GP3, 11 total switch inputs
- **Mini6**: Uses unusual pins (board.LED, board.VBUS_SENSE) for switches
- **NANO4**: 4 switches using a subset of STD10/Mini6 pins (GP1, board.LED, GP9, GP10)
- **DUO2**: 2 switches (GP11, GP9), 4 DIP switches (GP0-GP3), segmented LCD (no ST7789)
- **ONE1**: 1 switch (GP11), 2 DIP switches (GP2-GP3), segmented LCD (no ST7789)

Detection happens before config loading, so the same `code.py` works on all devices.

### Configuration

- **`config.json`** — User configuration (optional). If present, always used.
- **Built-in defaults** — If no config.json, firmware uses basic numbered buttons matching detected device's button count.

The `config-one1.json`, `config-duo2.json`, `config-mini6.json`, and `config-nano4.json` files in the repo are templates/examples for ONE, DUO2, Mini6, and NANO4 users to copy to their device as `config.json`.

---

## Platform

All MIDI Captain variants use:
- **MCU:** RP2040 (Raspberry Pi Pico platform)
- **CircuitPython:** 7.3.1 (verified)
- **Board ID:** `raspberry_pi_pico`

---

## STD10 (10-Switch)

### Physical Layout

```
┌─────────────────────────────────────────────────────────┐
│                      [DISPLAY]                          │
│                       240×240                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌───┐   ┌───┐   ┌───┐   ┌───┐   ┌───┐               │
│   │ 1 │   │ 2 │   │ 3 │   │ 4 │   │ ▼ │   [ENCODER]   │
│   └───┘   └───┘   └───┘   └───┘   └───┘               │
│   LED 0   LED 1   LED 2   LED 3   LED 4               │
│                                                         │
│   ┌───┐   ┌───┐   ┌───┐   ┌───┐   ┌───┐               │
│   │ A │   │ B │   │ C │   │ D │   │ ▲ │               │
│   └───┘   └───┘   └───┘   └───┘   └───┘               │
│   LED 5   LED 6   LED 7   LED 8   LED 9               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Switch Mapping

| Index | Label | GPIO Pin | CC Number | LED Index |
|-------|-------|----------|-----------|-----------|
| 0 | Encoder Push | GP0 | CC14 | None |
| 1 | 1 | GP1 | CC20 | 0 |
| 2 | 2 | GP25 | CC21 | 1 |
| 3 | 3 | GP24 | CC22 | 2 |
| 4 | 4 | GP23 | CC23 | 3 |
| 5 | Down (▼) | GP20 | CC24 | 4 |
| 6 | A | GP9 | CC25 | 5 |
| 7 | B | GP10 | CC26 | 6 |
| 8 | C | GP11 | CC27 | 7 |
| 9 | D | GP18 | CC28 | 8 |
| 10 | Up (▲) | GP19 | CC29 | 9 |

**Note:** Switch index 0 (encoder push) has no LED. Switch-to-LED conversion: `led_idx = switch_idx - 1` for indices 1-10.

### NeoPixels

- **Pin:** GP7
- **Count:** 30 (3 LEDs per switch × 10 switches)
- **Chain Order:** LEDs 0-4 = top row, LEDs 5-9 = bottom row
- **Per-Switch:** 3 consecutive pixels (e.g., switch 1 = pixels 0-2)

### Rotary Encoder

- **Pin A:** GP2
- **Pin B:** GP3
- **Push:** GP0 (same as switch index 0)

### Expression Pedals

- **EXP1:** A1 (analog input)
- **EXP2:** A2 (analog input)
- **Battery:** A3 (analog input, for voltage monitoring)

### Display

- **Controller:** ST7789
- **Resolution:** 240 × 240 pixels
- **Interface:** SPI

| Signal | GPIO Pin |
|--------|----------|
| DC | GP12 |
| CS | GP13 |
| SCK/CLK | GP14 |
| MOSI | GP15 |
| PWM (backlight) | GP8 (declared, not used in code) |
| Reset | None (not connected) |

**ST7789 Parameters:**
```python
ST7789(spi, width=240, height=240, rowstart=80, rotation=180)
```

### Serial MIDI

- **TX:** GP16
- **RX:** GP17
- **Baud:** 31250
- **Timeout:** 0 (non-blocking; the OEM firmware used 0.003s, which made every idle `receive()` block for 3 ms)

---

## Mini6 (6-Switch)

### Physical Layout

```
┌─────────────────────────────────────┐
│            [DISPLAY]                │
│             240×240                 │
├─────────────────────────────────────┤
│                                     │
│   ┌───┐       ┌───┐       ┌───┐    │
│   │TL │       │TM │       │TR │    │
│   └───┘       └───┘       └───┘    │
│                                     │
│   ┌───┐       ┌───┐       ┌───┐    │
│   │BL │       │BM │       │BR │    │
│   └───┘       └───┘       └───┘    │
│                                     │
└─────────────────────────────────────┘
```

### Switch Mapping

| Position | GPIO Pin | Notes |
|----------|----------|-------|
| Top-Left (TL) | GP1 | Also used as boot mode pin |
| Top-Middle (TM) | board.LED | Repurposed as input |
| Top-Right (TR) | board.VBUS_SENSE | Repurposed as input |
| Bottom-Left (BL) | GP9 | — |
| Bottom-Middle (BM) | GP10 | — |
| Bottom-Right (BR) | GP11 | — |

**Note:** `board.LED` and `board.VBUS_SENSE` are unusual pin assignments — the hardware intentionally repurposes these as footswitch inputs.

### NeoPixels

- **Pin:** GP7 (same as STD10)
- **Count:** 18 (3 LEDs per switch × 6 switches)

### Display

Same parameters as STD10:
- ST7789, 240×240, rowstart=80, rotation=180
- Same SPI pins (GP12-15)

### Not Present

- No rotary encoder
- No expression pedal inputs (TBD — may need probing)

---

## NANO4 (4-Switch)

> **Verified:** April 1, 2026 — probed on physical NANO 4 hardware using pin scanner, NeoPixel probe, and display probe scripts (`firmware/dev/experiments/nano4_probe.py`, `nano4_led_probe.py`, `nano4_display_probe.py`).

### Physical Layout

```
┌─────────────────────────────┐
│          [DISPLAY]          │
│           240×240           │
├─────────────────────────────┤
│                             │
│     ┌───┐       ┌───┐      │
│     │TL │       │TR │      │
│     └───┘       └───┘      │
│                             │
│     ┌───┐       ┌───┐      │
│     │BL │       │BR │      │
│     └───┘       └───┘      │
│                             │
└─────────────────────────────┘
```

### Switch Mapping

| Position | GPIO Pin | Notes |
|----------|----------|-------|
| Top-Left (TL) | GP1 | Also used as boot mode pin |
| Top-Right (TR) | board.LED (GP25) | Repurposed as input |
| Bottom-Left (BL) | GP9 | — |
| Bottom-Right (BR) | GP10 | — |

**Pin overlap with other devices:** All 4 pins are a subset of both STD10 and Mini6 switch pins. GP1, GP9, and GP10 are standard GPIO; `board.LED` (GP25) is repurposed as an input (same as Mini6 TM). Unlike Mini6, NANO4 does **not** use `board.VBUS_SENSE`.

### NeoPixels

- **Pin:** GP7 (same as STD10/Mini6)
- **Count:** 12 (3 LEDs per switch × 4 switches)
- **Chain Order:** TL → TR → BL → BR (LEDs 0-3, where each LED = 3 consecutive pixels)
- **Per-Switch:** 3 consecutive pixels in left → right → bottom order within each ring

### Display

Same parameters as STD10/Mini6:
- ST7789, 240×240, rowstart=80, rotation=180
- Same SPI pins (GP12-15)

### Serial MIDI

Not yet probed, but expected to use the same UART pins as STD10/Mini6 (GP16 TX, GP17 RX, 31250 baud) since the PCB design appears shared.

### Not Present

- No rotary encoder
- No expression pedal inputs

---

## DUO2 (2-Switch)

> **Verified:** April 2, 2026 — probed on physical DUO hardware using pin scanner, NeoPixel probe, display scan, and DIP switch probe scripts (`firmware/dev/experiments/duo2_probe.py`, `duo2_led_probe.py`, `duo2_display_scan.py`, `duo2_dip_probe.py`).

### Physical Layout

```
┌─────────────────────────┐
│     [Segmented LCD]     │
├─────────────────────────┤
│                         │
│         ┌───┐           │
│         │K1 │  (top)    │
│         └───┘           │
│                         │
│         ┌───┐           │
│         │K0 │  (bottom) │
│         └───┘           │
│                         │
│  DIP: [1][2][3][4]      │
└─────────────────────────┘
```

### Switch Mapping

| Position | GPIO Pin | Notes |
|----------|----------|-------|
| Bottom (KEY0) | GP11 | Also used as boot mode pin on DUO2 |
| Top (KEY1) | GP9 | — |

**Connector:** USB-C (unlike USB-A on STD10/Mini6/NANO4).

### DIP Switches

4 DIP switches for mode/page selection:

| DIP | GPIO Pin | Default State |
|-----|----------|---------------|
| 1 | GP0 | LOW (closed) |
| 2 | GP1 | LOW (closed) |
| 3 | GP2 | LOW (closed) |
| 4 | GP3 | LOW (closed) |

Flipping a DIP switch changes its pin from LOW → HIGH.

### NeoPixels

- **Pin:** GP7 (same as all other devices)
- **Count:** 6 (3 LEDs per switch × 2 switches)
- **Chain Order:** KEY0 (bottom) → KEY1 (top)
- **Per-Switch:** 3 consecutive pixels; KEY0 segments: top → left → right; KEY1 segments: bottom → right → left

### Display (Segmented LCD via UART)

**Not a TFT.** The DUO2 uses a 3-digit 7-segment LCD driven by a separate display controller over UART. This is fundamentally different from the ST7789 pixel displays on STD10/Mini6/NANO4.

**Protocol** (reverse-engineered from OEM `midicaptain2s.mpy` via `duo2_oem_inspect.py`):

| Parameter | Value |
|-----------|-------|
| Interface | UART (TX=GP4, RX=GP5) |
| Baudrate | 9600 |
| Frame format | `0xA5 <seg1> <seg2> <seg3> 0x5A` (5 bytes) |
| Transmission | Send frame 3 times with 40ms inter-frame delay |
| Segment encoding | Standard 7-segment, bit 7 = decimal point |

**7-segment digit encoding** (`digits_hex` from OEM):

| Digit | Hex | Binary (gfedcba) |
|-------|-----|-------------------|
| 0 | 0x3F | 0111111 |
| 1 | 0x06 | 0000110 |
| 2 | 0x5B | 1011011 |
| 3 | 0x4F | 1001111 |
| 4 | 0x66 | 1100110 |
| 5 | 0x6D | 1101101 |
| 6 | 0x7D | 1111101 |
| 7 | 0x07 | 0000111 |
| 8 | 0x7F | 1111111 |
| 9 | 0x6F | 1101111 |
| dash | 0x40 | 1000000 |
| blank | 0x00 | 0000000 |
| dp | +0x80 | bit 7 set |

**OEM display patterns** (5-byte frames: header + 3 segments + footer):

| Pattern | Bytes | Meaning |
|---------|-------|---------|
| `hex_VER` | `A5 6D 86 06 5A` | "S1.2" (5, 1+dot, 1) |
| `hex_pc` | `A5 73 39 40 5A` | "PC-" |
| `hex_cc` | `A5 39 39 40 5A` | "CC-" |
| `hex_nt` | `A5 37 79 40 5A` | "nt-" |
| `hex_NA` | `A5 40 40 40 5A` | "---" |
| `hex_HID` | `A5 76 06 5E 5A` | "HId" |

**Gotchas:**
- The display controller has its own startup animation and shows "---" by default. No init sequence is needed — just send frames.
- The frame must be sent 3 times (matching OEM's `DP_SEND1`/`DP_SEND2`/`DP_SEND3` state machine). Sending once may not be reliable.
- The `0xA5`/`0x5A` header/footer are required — raw segment bytes without framing are ignored.
- GP5 reads HIGH at idle because it's the display controller's TX line (UART idle = HIGH).
- Common UART display protocols (TM1637, HT1621, MAX7219) do NOT work — this is a proprietary UART protocol.
- The protocol was discovered by importing the OEM module in the REPL, interrupting with Ctrl+C, and inspecting `midicaptain2s.uart`, `midicaptain2s.display_buf`, and `midicaptain2s.digits_hex`.

**Firmware status:** Integrated. `HAS_SEG_DISPLAY = True` (derived from `SEG_DISPLAY_TX_PIN`) enables the UART display via the `update_status()` abstraction, which extracts the last number from status text and sends it to the 3-digit LCD.

---

## ONE1 (1-Switch)

> **Verified:** April 3, 2026 — probed on physical ONE hardware using pin scanner, NeoPixel probe, and DIP switch probe scripts (`firmware/dev/experiments/one1_probe.py`, `one1_led_probe.py`, `one1_dip_probe.py`).

### Physical Layout

```
┌─────────────────────────┐
│     [Segmented LCD]     │
├─────────────────────────┤
│                         │
│         ┌───┐           │
│         │K0 │           │
│         └───┘           │
│                         │
│       DIP: [1][2]       │
└─────────────────────────┘
```

### Switch Mapping

| Position | GPIO Pin | Notes |
|----------|----------|-------|
| KEY0 | GP11 | Also used as boot mode pin on ONE1 |

**Connector:** USB-C (same as DUO2).

### DIP Switches

2 DIP switches for mode/page selection:

| DIP | GPIO Pin | Default State |
|-----|----------|---------------|
| 1 | GP2 | LOW (closed) |
| 2 | GP3 | LOW (closed) |

Flipping a DIP switch changes its pin from LOW → HIGH.

### NeoPixels

- **Pin:** GP7 (same as all other devices)
- **Count:** 3 (3 LEDs for the single switch)
- **Chain Order:** LEDs 0-2 map to KEY0

### Display (Segmented LCD via UART)

Same protocol as DUO2 — 3-digit 7-segment LCD driven via UART (TX=GP4, RX=GP5, 9600 baud). See the DUO2 section above for full protocol details.

### Other Hardware

- No encoder
- No expression pedal inputs
- OEM firmware module: `midicaptain1s.mpy` (compiled, "1s" = 1 switch)

### GPIO Summary

| Pin | Function |
|-----|----------|
| GP2-GP3 | DIP switches (strongly pulled LOW by default) |
| GP4 | Display UART TX (9600 baud) |
| GP5 | Display UART RX (idle HIGH from display controller) |
| GP7 | NeoPixels (3 LEDs) |
| GP11 | KEY0 (only switch) |
| GP16 | Serial MIDI TX (31250 baud) |
| GP17 | Serial MIDI RX (31250 baud) |

### Serial MIDI

Confirmed from OEM inspection: GP16 TX, GP17 RX, 31250 baud (standard MIDI). Uses `uart2` in OEM firmware.

### Not Present

- No rotary encoder
- No expression pedal inputs
- No ST7789 pixel display (segmented LCD only, via UART)

---

## Boot Behavior

All devices use `boot.py` with a boot switch (GP1 on most devices, GP11 on DUO2/ONE1):

```python
# If GP1 is True at boot: disable USB drive, remount RW
# If GP1 is False: enable USB drive as MIDICAPTAIN, remount RO
```

- **Volume Label:** `CIRCUITPY` (changed from MIDICAPTAIN for extension compatibility)
- **Autoreload:** Disabled by default for performance
- GP1 is read at boot but can be used as a switch afterward

---

## CircuitPython Notes

### Version Compatibility

- **Target:** CircuitPython 7.x (7.3.1 verified)
- **Display API:** Use `display.show(group)` not `display.root_group` (7.x compatibility)
- **USB CDC:** Disconnects on reset — use auto-reconnect serial workflows

### Required Libraries

Install via `circup install -r requirements-circuitpython.txt`:
- `adafruit_midi`
- `adafruit_display_text`
- `adafruit_st7789`
- `neopixel`

---

## MIDI Protocol

### USB MIDI

- Device appears as USB MIDI device
- Uses `adafruit_midi` library
- Ports: `usb_midi.ports[0]` (in), `usb_midi.ports[1]` (out)

### CC Assignments (Current Demo)

| CC | Direction | Purpose |
|----|-----------|---------|
| 20-29 | TX/RX | Switches 1-10 (bidirectional) |

**TX (device → host):** 127 on press, 0 on release  
**RX (host → device):** >63 = LED on, ≤63 = LED dim/off

### Helmut's Original CC Mapping (Reference)

| CC | Purpose |
|----|---------|
| 11 | Rotary encoder |
| 12-13 | Expression pedals |
| 14 | Encoder push |
| 15-24 | Footswitches |
| 25 | Tuner mode toggle |

---

## Device Abstraction

Hardware constants are defined in `firmware/dev/devices/`:

```python
# firmware/dev/devices/std10.py
from devices.std10 import (
    LED_PIN, LED_COUNT,
    SWITCH_PINS,
    switch_to_led,
    DISPLAY_WIDTH, DISPLAY_HEIGHT,
    # ... etc
)
```

See [std10.py](../firmware/dev/devices/std10.py) for complete definitions.
