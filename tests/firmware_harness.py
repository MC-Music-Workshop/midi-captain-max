"""
Desktop harness for the real firmware/dev/code.py.

`boot_pedal(cfg, monkeypatch, tmp_path)` runs code.py top to bottom on desktop mocks,
stopping just before its `while True:` main loop, and returns a `Pedal`: the booted
module namespace plus helpers to press switches, advance time, and read what the
firmware sent (MIDI), lit (NeoPixels) and printed (serial console).

Everything is the shipped firmware code; only the hardware is fake:
  - adafruit_midi -> FakeMIDI (records send(), queues receive()) with real-shaped
    ControlChange / ProgramChange / NoteOn / NoteOff classes
  - board, digitalio, neopixel, rotaryio, analogio, usb_midi -> tests/mocks (via conftest)
  - display / font / ST7789 / busio libs -> MagicMock; usb_hid has no devices
  - /config.json -> your cfg dict; any other absolute path -> OSError (like a missing file)
  - time.monotonic -> a manual Clock (pedal.clock.t); time.sleep -> no-op

Typical use in a test (the `boot` fixture is in tests/conftest.py):

    pedal = boot(cfg)                 # cfg: a full config dict (device, pages, ...)
    pedal.tap(1)                      # switch index (STD10: 0 = encoder push, 1-10 = footswitches)
    assert pedal.sent() == [cc(20, 127)]
    pedal.hold(0, 2.0)                # press, advance 2 s, release
    pedal["button_states"][10].state  # any code.py global
    pedal.serial()                    # everything code.py printed, boot included

See also: emulator/ (Wokwi) runs the same code.py on simulated hardware, and
tests/test_wokwi_scenarios.py replays those scenarios here.
"""

import builtins
import contextlib
import io
import json
import sys
import time
import types
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
FW = REPO / "firmware" / "dev"
_CODE = (FW / "code.py").read_text()
BOOT_SRC = _CODE[:_CODE.index("\nwhile True:\n")]


# --- adafruit_midi stand-in -------------------------------------------------

class _Msg:
    channel = None

    def __eq__(self, other):
        return type(self) is type(other) and vars(self) == vars(other)

    def __repr__(self):
        return type(self).__name__ + str(vars(self))


class ControlChange(_Msg):
    def __init__(self, control, value, channel=None):
        self.control, self.value, self.channel = control, value, channel


class ProgramChange(_Msg):
    def __init__(self, patch, channel=None):
        self.patch, self.channel = patch, channel


class NoteOn(_Msg):
    def __init__(self, note, velocity=127, channel=None):
        self.note, self.velocity, self.channel = note, velocity, channel


class NoteOff(_Msg):
    def __init__(self, note, velocity=0, channel=None):
        self.note, self.velocity, self.channel = note, velocity, channel


class SystemExclusive(_Msg):
    pass


class FakeMIDI:
    """adafruit_midi.MIDI stand-in. code.py builds two: USB first, then DIN."""
    instances = []

    def __init__(self, *args, **kwargs):
        self.sent = []
        self.rx = []
        FakeMIDI.instances.append(self)

    def send(self, msg, channel=None):
        self.sent.append((msg, channel))

    def receive(self):
        return self.rx.pop(0) if self.rx else None


def _midi_modules():
    pkg = types.ModuleType("adafruit_midi")
    pkg.MIDI = FakeMIDI
    mods = {"adafruit_midi": pkg}
    for sub, cls in (("control_change", ControlChange), ("program_change", ProgramChange),
                     ("note_on", NoteOn), ("note_off", NoteOff),
                     ("system_exclusive", SystemExclusive)):
        m = types.ModuleType("adafruit_midi." + sub)
        setattr(m, cls.__name__, cls)
        mods["adafruit_midi." + sub] = m
    return mods


def cc(control, value, ch=0):
    """Expected entry in Pedal.sent() for a CC on 0-based channel `ch`."""
    return (ControlChange(control, value), ch)


# --- harness ----------------------------------------------------------------

class Clock:
    """Manual time.monotonic(): advance with `pedal.clock.t += seconds`."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Pedal:
    """A booted code.py namespace plus helpers. Index globals with pedal["name"]."""

    def __init__(self, ns, clock, serial):
        self.ns = ns
        self.clock = clock
        self._serial = serial
        self.usb = FakeMIDI.instances[0]

    def __getitem__(self, name):
        return self.ns[name]

    def serial(self):
        """Everything code.py printed so far (boot banner included)."""
        return self._serial.getvalue()

    def leds(self):
        return list(self.ns["pixels"]._pixels)

    def sent(self):
        """USB MIDI sent since the last call, as [(msg, channel), ...]; clears it."""
        out = list(self.usb.sent)
        self.usb.sent.clear()
        return out

    def loop(self):
        """One main-loop pass of the button work (switches, deferred repaints, flash timers, LED animations)."""
        with contextlib.redirect_stdout(self._serial):
            self.ns["handle_switches"]()
            self.ns["flush_cc_step_updates"]()
            self.ns["update_pc_flash_timers"]()
            self.ns["update_led_animations"]()

    def set(self, switch, pressed):
        self.ns["switches"][switch].io.value = not pressed
        self.loop()

    def press(self, switch):
        self.set(switch, True)

    def release(self, switch):
        self.set(switch, False)

    def tap(self, switch):
        self.press(switch)
        self.release(switch)

    def advance(self, seconds):
        """Move the clock and run a loop pass (fires long-press thresholds, flash expiry)."""
        self.clock.t += seconds
        self.loop()

    def hold(self, switch, seconds):
        self.press(switch)
        self.advance(seconds)
        self.release(switch)

    def receive(self, msg):
        """Process one incoming MIDI message as if it arrived on USB."""
        with contextlib.redirect_stdout(self._serial):
            self.ns["_process_midi_msg"](msg)
            self.ns["flush_cc_step_updates"]()


def boot_pedal(cfg, monkeypatch, tmp_path):
    """Boot code.py with `cfg` as /config.json. Returns a Pedal."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))
    real_open = builtins.open

    def fake_open(path, *a, **kw):
        if path == "/config.json":
            return real_open(cfg_path, *a, **kw)
        if isinstance(path, str) and path.startswith("/") and not path.startswith(str(REPO)) \
                and not path.startswith(str(tmp_path)):
            raise OSError("no such file on mock device: " + path)
        return real_open(path, *a, **kw)

    monkeypatch.setattr(builtins, "open", fake_open)
    for name, mod in _midi_modules().items():
        monkeypatch.setitem(sys.modules, name, mod)
    for name in ("displayio", "adafruit_display_text", "adafruit_display_text.label",
                 "adafruit_bitmap_font", "adafruit_bitmap_font.bitmap_font",
                 "adafruit_st7789", "terminalio", "busio"):
        monkeypatch.setitem(sys.modules, name, mock.MagicMock())
    hid = types.ModuleType("usb_hid")
    hid.devices = []
    monkeypatch.setitem(sys.modules, "usb_hid", hid)
    mc = types.ModuleType("microcontroller")
    mc.nvm = bytearray(1)
    monkeypatch.setitem(sys.modules, "microcontroller", mc)
    monkeypatch.syspath_prepend(str(FW))
    clock = Clock()
    monkeypatch.setattr(time, "monotonic", clock)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    FakeMIDI.instances = []
    serial = io.StringIO()
    ns = {"__name__": "code_under_test"}
    with contextlib.redirect_stdout(serial):
        exec(compile(BOOT_SRC, str(FW / "code.py"), "exec"), ns)
    return Pedal(ns, clock, serial)
