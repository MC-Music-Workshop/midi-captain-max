# MIDI Captain Emulator Setup

This document describes how to test MIDI Captain firmware using software emulators instead of physical hardware.

## Overview

Testing MIDI Captain firmware without physical hardware is possible using **rp2040js-circuitpython**, a JavaScript-based emulator that runs actual CircuitPython firmware on a simulated Raspberry Pi Pico (RP2040).

### What You Can Test

- ✅ **Firmware logic** — All Python code execution
- ✅ **MIDI communication** — USB MIDI and serial MIDI (via console output)
- ✅ **Configuration loading** — JSON config parsing and validation
- ✅ **Button state logic** — Toggle, momentary, host override
- ✅ **Switch scanning** — GPIO input simulation
- ✅ **Code deployment** — Full firmware + libraries + config
- ✅ **Automated testing** — CI/CD integration
- ✅ **Device detection** — STD10 vs Mini6 auto-detection

### Limitations

- ❌ **NeoPixel visual output** — LEDs don't render visually (code runs, verify via print statements)
- ❌ **ST7789 display rendering** — Display doesn't show graphics (verify via console logs)
- ⚠️ **MIDI device emulation** — MIDI packets appear as console output, not as actual MIDI devices

**Workaround**: Add print statements in your firmware to log LED colors, display updates, and MIDI messages to the console for verification.

## Tools

### 1. rp2040js-circuitpython (Recommended for CI/CD)

A headless command-line emulator that runs real CircuitPython firmware.

**Pros:**
- Runs actual `.uf2` CircuitPython firmware
- Headless operation for CI/CD pipelines
- GDB debugging support
- Console/REPL access
- Filesystem injection (config.json, code.py)

**Cons:**
- No visual output (NeoPixels, displays)
- Requires Node.js

**GitHub**: https://github.com/wokwi/rp2040js-circuitpython

### 2. Wokwi (Browser-based Alternative)

An interactive, visual simulator in the browser.

**Pros:**
- Visual simulation of some components
- Interactive debugging
- Easy to use
- No local installation

**Cons:**
- Requires internet connection
- Monthly simulation time limits (free tier)
- Less suitable for automated CI testing

**Website**: https://wokwi.com/

## Installation

### Prerequisites

- **Node.js** 18+ (for rp2040js-circuitpython)
- **CircuitPython 7.3.1 UF2** for Raspberry Pi Pico

### Install rp2040js-circuitpython

```bash
# Clone the emulator repository
git clone https://github.com/wokwi/rp2040js-circuitpython.git
cd rp2040js-circuitpython

# Install dependencies
npm install

# Download CircuitPython 7.3.1 UF2 (if not already present)
# Visit: https://circuitpython.org/board/raspberry_pi_pico/
# Download: adafruit-circuitpython-raspberry_pi_pico-en_US-7.3.1.uf2
```

### Prepare MIDI Captain Firmware

```bash
# Navigate to your MIDI Captain project
cd /path/to/midi-captain-max

# Create a filesystem image directory
mkdir -p emulator/fs

# Copy firmware files to the filesystem directory
cp -r firmware/dev/* emulator/fs/

# Ensure config.json exists
cp firmware/dev/config.json emulator/fs/config.json

# Optional: Add debug print statements to code.py for testing
```

## Usage

### Basic Usage

```bash
cd rp2040js-circuitpython

# Run the emulator with CircuitPython firmware
npm start -- --image=adafruit-circuitpython-raspberry_pi_pico-en_US-7.3.1.uf2 \
            --fs=/path/to/midi-captain-max/emulator/fs
```

The emulator will:
1. Boot CircuitPython
2. Load your firmware from `emulator/fs/code.py`
3. Display console output
4. Provide a REPL prompt

### Automated Testing

Create a test script to verify expected output:

```bash
# emulator/test.sh
#!/bin/bash

cd rp2040js-circuitpython

# Run emulator and capture output
timeout 30 npm start -- \
    --image=adafruit-circuitpython-raspberry_pi_pico-en_US-7.3.1.uf2 \
    --fs=/path/to/midi-captain-max/emulator/fs \
    > emulator.log 2>&1

# Verify expected output
if grep -q "MIDI CAPTAIN CUSTOM FIRMWARE" emulator.log; then
    echo "✅ Firmware booted successfully"
else
    echo "❌ Firmware boot failed"
    exit 1
fi

if grep -q "Config loaded" emulator.log; then
    echo "✅ Config loaded successfully"
else
    echo "❌ Config load failed"
    exit 1
fi
```

### Debug Mode

To enable verbose debugging:

```javascript
// Add to emulator/debug-config.json
{
  "debug": {
    "uart": true,
    "gpio": true,
    "spi": true
  }
}
```

## Testing Strategies

### 1. Unit Testing (Current Approach)

The project uses **pytest with mocks** for fast unit testing:

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run unit tests
python3 -m pytest
```

**Use for:**
- Testing individual functions and classes
- Testing button logic, color utilities, config parsing
- Fast feedback during development

### 2. Emulator Testing (Integration Testing)

Use **rp2040js-circuitpython** for integration testing:

```bash
# Test full firmware boot
./emulator/test.sh

# Test specific scenarios with custom configs
cp emulator/configs/test-toggle.json emulator/fs/config.json
./emulator/test.sh
```

**Use for:**
- Testing full firmware integration
- Verifying device detection (STD10 vs Mini6)
- Testing MIDI message flow
- Simulating button presses (via GPIO injection)

### 3. Hardware Testing (Final Validation)

Deploy to actual hardware for final validation:

```bash
# Deploy to device
./tools/deploy.sh

# Monitor serial console
screen /dev/cu.usbmodem* 115200
```

**Use for:**
- Visual LED/display verification
- Real MIDI device communication
- Performance testing
- Stage reliability testing

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/emulator-test.yml
name: Emulator Tests

on: [push, pull_request]

jobs:
  emulator-test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'

      - name: Clone emulator
        run: |
          git clone https://github.com/wokwi/rp2040js-circuitpython.git
          cd rp2040js-circuitpython
          npm install

      - name: Download CircuitPython UF2
        run: |
          wget https://downloads.circuitpython.org/bin/raspberry_pi_pico/en_US/adafruit-circuitpython-raspberry_pi_pico-en_US-7.3.1.uf2

      - name: Prepare firmware
        run: |
          mkdir -p emulator/fs
          cp -r firmware/dev/* emulator/fs/

      - name: Run emulator test
        run: |
          cd rp2040js-circuitpython
          timeout 30 npm start -- \
            --image=../adafruit-circuitpython-raspberry_pi_pico-en_US-7.3.1.uf2 \
            --fs=../emulator/fs \
            > ../emulator.log 2>&1 || true

      - name: Verify output
        run: |
          if grep -q "MIDI CAPTAIN CUSTOM FIRMWARE" emulator.log; then
            echo "✅ Firmware boot successful"
          else
            echo "❌ Firmware boot failed"
            cat emulator.log
            exit 1
          fi

      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: emulator-logs
          path: emulator.log
```

## Debugging Tips

### 1. Add Debug Output

Modify `firmware/dev/code.py` to add debug prints:

```python
# At the start of code.py
print("=== DEBUG: Firmware starting ===")

# Before MIDI operations
print(f"DEBUG: Sending MIDI CC {cc_num} value {value}")

# After button press
print(f"DEBUG: Button {idx} pressed, state={button.state.is_on}")

# After LED update
print(f"DEBUG: LED {idx} set to color {color}")
```

### 2. Capture Console Output

```bash
# Run emulator and save full output
npm start -- --image=firmware.uf2 --fs=./fs 2>&1 | tee output.log

# Search for specific events
grep "DEBUG:" output.log
grep "MIDI" output.log
grep "Error" output.log
```

### 3. GDB Debugging

rp2040js supports GDB for advanced debugging:

```bash
# Start emulator with GDB server
npm start -- --image=firmware.uf2 --fs=./fs --gdb

# In another terminal, connect with GDB
arm-none-eabi-gdb
(gdb) target remote localhost:3333
(gdb) break main
(gdb) continue
```

## Device Configuration

### Testing STD10 (10-switch)

```json
{
  "device": "std10",
  "buttons": [
    {"label": "BTN1", "cc": 20, "color": "red"},
    {"label": "BTN2", "cc": 21, "color": "green"},
    {"label": "BTN3", "cc": 22, "color": "blue"},
    {"label": "BTN4", "cc": 23, "color": "yellow"},
    {"label": "BTN5", "cc": 24, "color": "cyan"},
    {"label": "BTN6", "cc": 25, "color": "magenta"},
    {"label": "BTN7", "cc": 26, "color": "orange"},
    {"label": "BTN8", "cc": 27, "color": "purple"},
    {"label": "BTN9", "cc": 28, "color": "white"},
    {"label": "BTN10", "cc": 29, "color": "red"}
  ]
}
```

### Testing Mini6 (6-switch)

```json
{
  "device": "mini6",
  "buttons": [
    {"label": "BTN1", "cc": 20, "color": "red"},
    {"label": "BTN2", "cc": 21, "color": "green"},
    {"label": "BTN3", "cc": 22, "color": "blue"},
    {"label": "BTN4", "cc": 23, "color": "yellow"},
    {"label": "BTN5", "cc": 24, "color": "cyan"},
    {"label": "BTN6", "cc": 25, "color": "magenta"}
  ]
}
```

## Troubleshooting

### Emulator Won't Start

**Problem**: `npm start` fails with errors

**Solutions**:
- Verify Node.js version: `node --version` (needs 18+)
- Reinstall dependencies: `rm -rf node_modules && npm install`
- Check UF2 file exists and is CircuitPython 7.3.1

### Firmware Won't Boot

**Problem**: Emulator starts but firmware doesn't run

**Solutions**:
- Check `code.py` exists in filesystem: `ls emulator/fs/code.py`
- Verify CircuitPython 7.x syntax (no walrus operator, no dict unpacking)
- Check for import errors in console output
- Ensure all dependencies are in `emulator/fs/lib/`

### No MIDI Output

**Problem**: MIDI messages not appearing in console

**Solutions**:
- Add print statements before MIDI send: `print(f"Sending MIDI: CC{cc} = {val}")`
- Check USB MIDI initialization: verify `usb_midi.ports` exists
- Emulator may not route MIDI to host (verify via print statements)

### Console Output Garbled

**Problem**: Console shows strange characters or formatting

**Solutions**:
- REPL control codes may interfere with log parsing
- Use `--no-repl` flag if available
- Filter output: `npm start | grep -v "^\x1b"`

## Next Steps

1. **Try the emulator locally**:
   ```bash
   ./emulator/setup.sh
   ./emulator/test.sh
   ```

2. **Add emulator tests to CI**:
   - Copy the GitHub Actions example above to `.github/workflows/emulator-test.yml`
   - Push and verify tests pass

3. **Extend test coverage**:
   - Add test scenarios for different configs
   - Test device auto-detection
   - Test MIDI message patterns

4. **Contribute improvements**:
   - Report emulator issues to https://github.com/wokwi/rp2040js-circuitpython
   - Share successful test patterns with the community

## References

- **rp2040js-circuitpython**: https://github.com/wokwi/rp2040js-circuitpython
- **Wokwi Docs**: https://docs.wokwi.com/
- **CircuitPython Downloads**: https://circuitpython.org/board/raspberry_pi_pico/
- **RP2040 Datasheet**: https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf
- **MIDI Captain Hardware Reference**: [docs/hardware-reference.md](hardware-reference.md)

---

**Note**: This emulator setup is a **spike/experiment** to enable testing without hardware. It's not meant to replace hardware testing entirely, but to complement it for faster development cycles and CI automation.
