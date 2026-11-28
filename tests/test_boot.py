"""
Tests for the USB drive label and editor keep-drive flag at boot.

Two layers:
- core/boot_util.py helpers (apply_drive_label, consume_keep_drive_flag) on
  plain fakes.
- firmware/dev/boot.py itself, exec'd with fake storage / microcontroller /
  supervisor modules, for the wiring: which boots show the drive, when the
  label is written, and that the one-shot flag is always cleared.
"""

import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "firmware" / "dev"))

from core import boot_util, config as core_config  # noqa: E402
from core.boot_util import KEEP_DRIVE_BYTE, apply_drive_label, consume_keep_drive_flag  # noqa: E402

BOOT_PY = Path(__file__).parent.parent / "firmware" / "dev" / "boot.py"


class FakeMount:
    def __init__(self, label, storage):
        self._label = label
        self._storage = storage

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        self._storage.calls.append(("set_label", value))
        if self._storage.label_error is not None:
            raise self._storage.label_error
        if self._storage.host_readonly is False:
            # CircuitPython can only write while it holds the filesystem RW.
            raise OSError("Read-only filesystem")
        self._label = value


class FakeStorage:
    """storage module stand-in. host_readonly mirrors remount(readonly=...)."""

    def __init__(self, label="CIRCUITPY"):
        self.calls = []
        self.label_error = None
        self.remount_error = None
        self.host_readonly = False  # boot default: host can write, CP can't
        self.mount = FakeMount(label, self)
        self.usb_drive_disabled = False

    def getmount(self, path):
        assert path == "/"
        return self.mount

    def remount(self, path, readonly=False, **kwargs):
        assert path == "/"
        if kwargs:
            raise TypeError("unexpected keyword argument")  # CP 7.x: no label=
        self.calls.append(("remount", readonly))
        if self.remount_error is not None:
            raise self.remount_error
        # readonly=False → CP writable, host read-only; True → the reverse.
        self.host_readonly = not readonly

    def disable_usb_drive(self):
        self.calls.append(("disable_usb_drive",))
        self.usb_drive_disabled = True


# ── apply_drive_label ─────────────────────────────────────────────────────────

def test_apply_label_none_leaves_drive_alone():
    s = FakeStorage("STAGELEFT")
    assert apply_drive_label(s, None) is False
    assert s.calls == []
    assert s.mount.label == "STAGELEFT"


def test_apply_label_matching_label_writes_nothing():
    s = FakeStorage("MYBOARD")
    assert apply_drive_label(s, "MYBOARD") is False
    assert s.calls == []


def test_apply_label_writes_when_different_and_hands_write_back_to_host():
    s = FakeStorage("CIRCUITPY")
    assert apply_drive_label(s, "MYBOARD") is True
    assert s.mount.label == "MYBOARD"
    assert s.calls == [("remount", False), ("set_label", "MYBOARD"), ("remount", True)]
    assert s.host_readonly is False


def test_apply_label_second_boot_is_a_no_op():
    s = FakeStorage("CIRCUITPY")
    apply_drive_label(s, "MYBOARD")
    s.calls.clear()
    assert apply_drive_label(s, "MYBOARD") is False
    assert s.calls == []


def test_apply_label_failed_write_still_restores_host_write_access(capsys):
    s = FakeStorage("CIRCUITPY")
    s.label_error = OSError("label write failed")
    assert apply_drive_label(s, "MYBOARD") is False
    assert s.calls[-1] == ("remount", True)
    assert s.host_readonly is False
    assert s.mount.label == "CIRCUITPY"
    assert "Drive label warning" in capsys.readouterr().out


def test_apply_label_never_raises():
    s = FakeStorage("CIRCUITPY")
    s.remount_error = RuntimeError("Cannot remount")
    assert apply_drive_label(s, "MYBOARD") is False

    class Broken:
        def getmount(self, path):
            raise OSError("no fs")

    assert apply_drive_label(Broken(), "MYBOARD") is False


# ── consume_keep_drive_flag ───────────────────────────────────────────────────

class CountingNvm(bytearray):
    """nvm stand-in that counts writes (each one erases a flash sector)."""

    writes = 0

    def __setitem__(self, i, v):
        self.writes += 1
        super().__setitem__(i, v)


def test_keep_drive_flag_true_once_then_cleared():
    nvm = CountingNvm(4)
    nvm[KEEP_DRIVE_BYTE] = 1
    nvm.writes = 0
    assert consume_keep_drive_flag(nvm) is True
    assert nvm[KEEP_DRIVE_BYTE] == 0
    assert consume_keep_drive_flag(nvm) is False


def test_keep_drive_flag_unset_writes_nothing():
    nvm = CountingNvm(4)
    assert consume_keep_drive_flag(nvm) is False
    assert nvm.writes == 0


def test_keep_drive_flag_does_not_touch_boot_flag_byte():
    nvm = CountingNvm(4)
    nvm[0] = 1
    nvm[KEEP_DRIVE_BYTE] = 1
    consume_keep_drive_flag(nvm)
    assert nvm[0] == 1


def test_keep_drive_flag_never_raises():
    assert consume_keep_drive_flag(bytearray(0)) is False


# ── boot.py wiring ────────────────────────────────────────────────────────────

@pytest.fixture
def run_boot(monkeypatch, tmp_path):
    """Exec boot.py with fakes: run_boot(cfg, label=, switch_held=, keep_flag=).

    cfg: dict written as config.json, a str written verbatim (broken JSON),
    or None for no config.json. Returns (storage, nvm, printed output).
    """
    import digitalio

    def _run(cfg, label="CIRCUITPY", switch_held=False, keep_flag=False):
        config_path = tmp_path / "config.json"
        if isinstance(cfg, dict):
            config_path.write_text(json.dumps(cfg))
        elif isinstance(cfg, str):
            config_path.write_text(cfg)
        elif config_path.exists():
            config_path.unlink()

        storage = FakeStorage(label)
        nvm = bytearray(256)
        nvm[KEEP_DRIVE_BYTE] = 1 if keep_flag else 0
        micro = types.SimpleNamespace(nvm=nvm)
        supervisor = types.SimpleNamespace(disable_autoreload=lambda: None)

        # boot.py does `from config import load_config` off /core; point it at
        # the real module but read our tmp config.json.
        fake_config = types.ModuleType("config")
        fake_config.__dict__.update(core_config.__dict__)
        fake_config.load_config = lambda path="/config.json", *a, **k: core_config.load_config(
            str(config_path), *a, **k
        )

        monkeypatch.setitem(sys.modules, "storage", storage)
        monkeypatch.setitem(sys.modules, "microcontroller", micro)
        monkeypatch.setitem(sys.modules, "supervisor", supervisor)
        monkeypatch.setitem(sys.modules, "config", fake_config)
        monkeypatch.setitem(sys.modules, "boot_util", boot_util)
        monkeypatch.setattr(sys, "path", list(sys.path))  # boot.py inserts /core

        original_init = digitalio.DigitalInOut.__init__

        def init(self, pin):
            original_init(self, pin)
            self._value = not switch_held  # pull-up: LOW = pressed

        monkeypatch.setattr(digitalio.DigitalInOut, "__init__", init)

        exec(compile(BOOT_PY.read_text(), str(BOOT_PY), "exec"), {"__name__": "__main__"})
        return storage, nvm

    return _run


def test_boot_performance_mode_hides_drive_and_leaves_label(run_boot):
    storage, nvm = run_boot({"usb_drive_name": "MYBOARD"})
    assert storage.usb_drive_disabled
    assert ("remount", False) not in storage.calls
    assert storage.mount.label == "CIRCUITPY"  # applied the next time it's shown


def test_boot_switch_held_renames_to_configured_name(run_boot):
    storage, _ = run_boot({"usb_drive_name": "My Board"}, switch_held=True)
    assert not storage.usb_drive_disabled
    assert storage.mount.label == "MYBOARD"
    assert storage.host_readonly is False


def test_boot_dev_mode_renames(run_boot):
    storage, _ = run_boot({"usb_drive_name": "STAGE_L", "dev_mode": True})
    assert not storage.usb_drive_disabled
    assert storage.mount.label == "STAGE_L"


def test_boot_matching_label_never_remounts(run_boot):
    storage, _ = run_boot({"usb_drive_name": "MYBOARD"}, label="MYBOARD", switch_held=True)
    assert [c for c in storage.calls if c[0] == "remount"] == []


@pytest.mark.parametrize("label", ["CIRCUITPY", "STAGELEFT"])
def test_boot_no_drive_name_leaves_label_alone(run_boot, label):
    """CIRCUITPY drives and drives renamed by hand keep their name."""
    storage, _ = run_boot({"dev_mode": True}, label=label)
    assert storage.mount.label == label
    assert [c for c in storage.calls if c[0] == "remount"] == []


@pytest.mark.parametrize("cfg", ["{ not json", None])
def test_boot_broken_or_missing_config_leaves_label_alone(run_boot, cfg):
    storage, _ = run_boot(cfg, label="STAGELEFT", switch_held=True)
    assert storage.mount.label == "STAGELEFT"
    assert storage.host_readonly is False


def test_boot_editor_flag_shows_drive_once_and_renames(run_boot):
    storage, nvm = run_boot({"usb_drive_name": "NEWNAME"}, keep_flag=True)
    assert not storage.usb_drive_disabled
    assert storage.mount.label == "NEWNAME"
    assert nvm[KEEP_DRIVE_BYTE] == 0


def test_boot_editor_flag_cleared_even_when_dev_mode_already_shows_drive(run_boot):
    """dev_mode short-circuits the `or`; the flag must still be consumed so a
    later performance-mode boot doesn't show the drive."""
    _, nvm = run_boot({"dev_mode": True}, keep_flag=True)
    assert nvm[KEEP_DRIVE_BYTE] == 0


def test_boot_editor_flag_cleared_when_switch_held(run_boot):
    _, nvm = run_boot({}, switch_held=True, keep_flag=True)
    assert nvm[KEEP_DRIVE_BYTE] == 0


def test_boot_failed_label_write_keeps_drive_writable(run_boot, monkeypatch):
    original = FakeStorage.__init__

    def init(self, label="CIRCUITPY"):
        original(self, label)
        self.label_error = OSError("boom")

    monkeypatch.setattr(FakeStorage, "__init__", init)
    storage, _ = run_boot({"usb_drive_name": "NEWNAME"}, switch_held=True)
    assert storage.mount.label == "CIRCUITPY"
    assert storage.host_readonly is False
