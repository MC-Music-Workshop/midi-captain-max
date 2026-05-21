"""
MIDI Captain boot.py

Runs once at device power-on/reset, before code.py.

CRITICAL: Autoreload is DISABLED for rock-solid live performance.
The device must NEVER reset unexpectedly during a gig. File changes
on the USB drive will not trigger reloads.

USB DRIVE — two modes, controlled by config.json:

  Performance Mode (default, dev_mode: false):
    Drive is hidden unless Switch 1 is held during boot.
    - Hold switch 1 (top-left) while powering on → USB drive appears
    - Release switch and reboot normally → USB hidden again

  Development Mode (dev_mode: true):
    Drive always mounts on boot — no switch needed.
    Convenient when iterating on firmware locally.

To reload after config/code changes:
- Send Ctrl+D over serial console
- Or power-cycle the device
"""

import board
import digitalio
import microcontroller
import storage
import supervisor
import time

# NVM byte 0 — "boot in progress" flag. Set to 1 here; code.py clears it
# to 0 once init reaches steady state (just before the main loop). If we
# read 1 on entry, the previous boot didn't complete — diagnose by
# compile-checking code.py below.
_BOOT_FLAG_BYTE = 0
_prev_boot_crashed = microcontroller.nvm[_BOOT_FLAG_BYTE] == 1
microcontroller.nvm[_BOOT_FLAG_BYTE] = 1

# DISABLED for live performance stability - no unexpected resets
# CP 7.x uses supervisor.disable_autoreload(), not runtime.autoreload
supervisor.disable_autoreload()

# Load config settings needed at boot time (drive name, dev mode, HID enable).
# boot.py runs before normal module search paths are established,
# so we add /core to sys.path explicitly.
usb_drive_name = "MIDICAPTAIN"  # Default fallback
dev_mode = False                # Default: performance mode
hid_enabled = False             # Default: HID not enabled
try:
    import sys
    sys.path.insert(0, "/core")
    from config import load_config, get_usb_drive_name, get_dev_mode

    cfg = load_config("/config.json")
    dev_mode = get_dev_mode(cfg)
    usb_drive_name = get_usb_drive_name(cfg)

    # Enable USB HID only if at least one button uses type="hid".
    # This keeps the USB descriptor clean for MIDI-only setups.
    hid_enabled = any(btn.get("type") == "hid" for btn in cfg.get("buttons", []))
except Exception:
    # If config fails to load, use safe defaults (performance mode, no HID)
    pass

# Compile-check code.py — only when the previous boot didn't complete.
# Healthy boots skip this entirely (compile() of ~1300-line code.py costs
# hundreds of ms). A SyntaxError in code.py leaves the device with a
# blank screen and no obvious failure signal — silent brick. On the
# *next* boot after such a crash, we land here, leave USB drive at
# CircuitPython's default (enabled, since we haven't called
# disable_usb_drive yet), and blink red SOS on NeoPixel 0 forever. User
# reads the error over serial, edits code.py via USB drive, power-cycles.
try:
    if _prev_boot_crashed:
        with open("/code.py") as _f:
            compile(_f.read(), "code.py", "exec")
except SyntaxError as _e:
    print(f"💀 code.py SyntaxError: {_e}")
    print("   USB drive enabled. Fix code.py via the drive and power-cycle.")
    import neopixel
    _pixels = neopixel.NeoPixel(board.GP7, 1, brightness=0.3, auto_write=True)
    _SHORT = 0.2
    _LONG = 0.6
    _GAP = 0.2
    _MSG_GAP = 1.5
    _RED = (255, 0, 0)
    _OFF = (0, 0, 0)
    # SOS = ... --- ... (3 short, 3 long, 3 short)
    _PATTERN = (_SHORT, _SHORT, _SHORT, _LONG, _LONG, _LONG, _SHORT, _SHORT, _SHORT)
    while True:
        for _dur in _PATTERN:
            _pixels[0] = _RED
            time.sleep(_dur)
            _pixels[0] = _OFF
            time.sleep(_GAP)
        time.sleep(_MSG_GAP)

# Enable USB HID (keyboard + mouse) if any configured button uses type="hid".
# Must be called before USB is fully initialized; boot.py is the only place
# where usb_hid.enable() has any effect.
if hid_enabled:
    try:
        import usb_hid
        usb_hid.enable((usb_hid.Device.KEYBOARD, usb_hid.Device.MOUSE))
        print("🎹 USB HID enabled (keyboard + mouse)")
    except Exception as e:
        print(f"⚠️  USB HID enable failed: {e}")

# Check if user is holding a switch during boot.
# DUO2/ONE1 use GP11 (KEY0) because GP1 is a DIP switch on those devices.
# All other devices use GP1 (switch 1).
# With pull-up: LOW (False) = pressed, HIGH (True) = not pressed.
boot_switch_pin = board.GP1
try:
    _device = cfg.get("device", "") if cfg else ""
    if _device in ("duo2", "one1"):
        boot_switch_pin = board.GP11
except Exception:
    pass

switch_1 = digitalio.DigitalInOut(boot_switch_pin)
switch_1.direction = digitalio.Direction.INPUT
switch_1.pull = digitalio.Pull.UP
time.sleep(0.05)  # Allow pull-up to stabilize before reading

switch_held = not switch_1.value          # True when switch is pressed
enable_usb_drive = dev_mode or switch_held  # dev_mode overrides switch gate


# CRITICAL: disable_usb_drive() must be called BEFORE any USB initialization.
# Always check the disable condition first; remount() would initialize USB.
if not enable_usb_drive:
    # Performance mode - hide USB drive completely
    # Drive won't appear on computer, preventing remount issues
    try:
        storage.disable_usb_drive()
        print("🔒 USB drive disabled (hold switch 1 during boot to enable)")
    except Exception as e:
        print(f"⚠️  USB disable failed: {e}")

# If USB is enabled, apply the custom drive label.
# This runs AFTER the disable check so USB only initializes when needed.
if enable_usb_drive:
    mode_label = "DEV MODE" if dev_mode else "switch held"
    print(f"🔓 USB DRIVE ENABLED as '{usb_drive_name}' ({mode_label})")
    if not dev_mode:
        print("   Release switch and reboot to hide drive")
    try:
        # readonly=True: CircuitPython is read-only, USB host has write access
        # (needed for config editor to save files to the device)
        storage.remount("/", readonly=True, label=usb_drive_name)
    except TypeError:
        # CircuitPython 7.x doesn't support label=; skip remount so the USB
        # host retains default write access
        pass
    except Exception as e:
        print(f"⚠️  Drive label warning: {e}")

# Clean up - switch will be available again in code.py
switch_1.deinit()
