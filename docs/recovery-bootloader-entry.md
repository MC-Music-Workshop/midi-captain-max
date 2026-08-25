# Manually entering the RP2040 bootloader

The Config Editor's **Advanced / Recovery → Reflash CircuitPython 7.3.1**
flow normally drives the device into the RP2040 ROM bootloader (`RPI-RP2`)
for you, using the device's CircuitPython serial REPL. If that fails — the
modal showed an error with a link to this page — your device couldn't be
reached over serial. The most common reasons:

- `boot.py` crashes before CircuitPython initialises USB CDC, so no serial
  port enumerates.
- Non-CircuitPython firmware is on the chip (no CDC serial at all).
- macOS / Windows hasn't claimed the device as a serial port (transient —
  unplug + replug usually fixes this).
- Multiple Adafruit-VID devices are connected and the wrong one was picked.

Below are two recovery paths in order of preference.

## Option A: serial REPL by hand (preferred if any CDC serial is alive)

Works as long as the device exposes a serial port (e.g. `/dev/tty.usbmodem*`
on macOS, `COM*` on Windows). This is the same sequence the GUI tries — if
the GUI failed because of a transient or path-mismatch issue, doing it
manually often succeeds.

1. Identify the serial port:
   - macOS / Linux: `ls /dev/tty.usbmodem*` (or `/dev/ttyACM*`)
   - Windows: open Device Manager → Ports (COM & LPT) → look for "USB Serial"
2. Connect with any terminal that speaks 115200 8N1:
   - macOS: `screen /dev/tty.usbmodemXXXX 115200`  (exit with `Ctrl-A K Y`)
   - Linux: `tio /dev/ttyACMX` or `screen /dev/ttyACMX 115200`
   - Windows: PuTTY in Serial mode, COM port from Device Manager, baud 115200
   - Cross-platform: install `tio` from your package manager
3. Once connected, press `Ctrl-C` to interrupt any running code. You should
   see a `>>>` REPL prompt.
4. Paste these three lines (one at a time, pressing Enter after each):

   ```python
   import microcontroller
   microcontroller.on_next_reset(microcontroller.RunMode.UF2)
   microcontroller.reset()
   ```

5. The device disconnects from the serial port and the `CIRCUITPY` drive
   unmounts. Within ~3 seconds an `RPI-RP2` drive appears.
6. Switch back to the Config Editor — the top-level "RPI-RP2 detected"
   banner should appear automatically. Click **Reflash CircuitPython 7.3.1**
   in the banner to finish the install.

## Option B: physical BOOTSEL (last resort)

Use this if Option A fails — i.e., the device exposes no usable serial
port at all. **Requires opening the Captain's enclosure.**

1. Power off and unplug the device.
2. Open the enclosure to expose the RP2040 module inside. On most Captain
   variants the RP2040 is a small board (Pico or Pico-compatible) with a
   tiny tactile button labelled `BOOTSEL` or `BOOT`.
3. Hold down the BOOTSEL button on the RP2040 module.
4. With BOOTSEL still held, connect USB to your computer.
5. Release BOOTSEL once a drive named `RPI-RP2` appears in Finder /
   Explorer.
6. Back in the Config Editor, the "RPI-RP2 detected" banner appears.
   Click **Reflash CircuitPython 7.3.1** to finish.

> ⚠️ Switch 1 / KEY0 (the top-left footswitch) does **not** trigger BOOTSEL
> on Captain devices. It's only used by the running CircuitPython firmware
> to expose the CIRCUITPY USB drive in performance mode. Holding it during
> power-on without a working CP firmware does nothing.

## After successful reflash

Once CircuitPython 7.3.1 is installed and CIRCUITPY remounts, click
**Install Firmware** in the editor to deploy MIDI Captain MAX onto the
fresh CP install. The bundled `.uf2` is the CODE_ONLY variant, so your
existing config and Max firmware files are preserved across the
CircuitPython reflash where possible.

## Coming from PaintAudio OEM FW5+?

FW5+ replaced the CircuitPython application with a C firmware (arduino-pico
core), so there is no REPL and Option A cannot work. Both FW5+ and
CircuitPython 7.3.1 support the **1200-baud touch** instead: opening the
device's serial port at 1200 baud and closing it reboots the chip into the
RP2040 ROM bootloader. The Config Editor detects FW5 pedals and does this for
you (banner → Migrate). Manual equivalent:
`stty -f /dev/cu.usbmodemXXXX 1200`, or PaintAudio's own
`MIDICAPTAINBOOT.HTML` (shipped on the FW5 pedal's drive) in Chrome/Edge.
No flash erase is needed before reflashing CircuitPython — CP auto-formats
FW5's leftover filesystem region on first boot (bench-verified). Back up the
pedal's drive first if you may want to return to OEM firmware.

## Still stuck?

Open an issue at
<https://github.com/MC-Music-Workshop/midi-captain-max/issues> with:

- Output of `boot_out.txt` from the device drive (if any).
- Result of `ls /Volumes/` (macOS) or `Get-Volume` (Windows) with the
  device plugged in.
- Which step above failed and how (no serial port, no `RPI-RP2`, etc.).
