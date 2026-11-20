"""
Tests for the hardware bench suite in tools/bench/ (pure logic only, no device).

- Every bench config passes config.schema.json and the firmware validator cleanly
- serial-stall.py's line counting and pass/fail evaluation
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).parent.parent
BENCH_DIR = REPO_ROOT / "tools" / "bench"
sys.path.insert(0, str(REPO_ROOT / "firmware" / "dev"))

from core.config import validate_config


def bench_configs():
  return sorted((BENCH_DIR / "configs").glob("*.json"))


@pytest.fixture(scope="module")
def validator():
  with open(REPO_ROOT / "config.schema.json") as f:
    return Draft7Validator(json.load(f))


def test_bench_configs_exist():
  assert bench_configs(), "no configs in tools/bench/configs/"


@pytest.mark.parametrize("path", bench_configs(), ids=lambda p: p.name)
def test_bench_config_matches_schema(validator, path):
  cfg = json.loads(path.read_text())
  errors = list(validator.iter_errors(cfg))
  assert errors == [], f"{path.name}: {errors[0].message}"


@pytest.mark.parametrize("path", bench_configs(), ids=lambda p: p.name)
def test_bench_config_validates_without_warnings(path, capsys):
  cfg = json.loads(path.read_text())
  button_count = max(len(p.get("buttons", [])) for p in cfg["pages"])
  out = validate_config(cfg, button_count=button_count)
  assert "[CONFIG WARN]" not in capsys.readouterr().out
  assert len(out["pages"]) == len(cfg["pages"])
  if "page_control" in cfg:
    assert "page_control" in out, "validator dropped page_control"


# serial-stall.py has a hyphen in its name, so load it by path.
_spec = importlib.util.spec_from_file_location("serial_stall", BENCH_DIR / "serial-stall.py")
serial_stall = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(serial_stall)


def test_count_page_lines():
  buf = b"[PAGE] CC100=1 -> page 1\r\n[MIDI RX] x\r\n[PAGE] CC100=0 -> page 0\r\n"
  assert serial_stall.count_page_lines(buf) == 2
  assert serial_stall.count_page_lines(b"") == 0


@pytest.mark.parametrize("mode,flips,lines,slow,probe,passed", [
  ("read", 200, 200, 0, None, True),
  ("read", 200, 198, 0, None, True),   # within default tolerance
  ("read", 200, 197, 0, None, False),  # lines lost
  ("read", 200, 200, 1, None, False),  # one slow send
  ("hold", 2000, 1726, 0, 10, True),   # host dropped output: informational only
  ("hold", 2000, 50, 0, 10, True),
  ("hold", 2000, 1726, 3, 10, False),
  ("hold", 2000, 1726, 0, 0, False),   # pedal silent after the hold: wedged
  ("hold", 2000, 1726, 0, None, False),
])
def test_evaluate(mode, flips, lines, slow, probe, passed):
  ok, summary = serial_stall.evaluate(mode, flips, lines, slow, probe=probe)
  assert ok is passed
  assert f"{flips} flips" in summary and f"lines {lines}" in summary
  if mode == "hold":
    assert f"probe {probe}/{serial_stall.PROBE_FLIPS}" in summary


class FakeSender:
  """Stands in for the sendmidi Popen: a pipe for stdin, a pipe for stderr."""

  def __init__(self, returncode=None):
    self.returncode = returncode
    r, w = os.pipe()
    self.stdin = os.fdopen(w, "wb")
    self._stdin_r = r
    er, self._err_w = os.pipe()
    os.set_blocking(er, False)
    self.stderr = os.fdopen(er, "rb")

  def poll(self):
    return self.returncode

  def sent(self):
    self.stdin.flush()
    os.set_blocking(self._stdin_r, False)
    return os.read(self._stdin_r, 4096)


def test_send_writes_one_command_line():
  sender = FakeSender()
  assert serial_stall.send(sender, 1) is None
  assert sender.sent() == b"ch 4 cc 100 1\n"


def test_send_reports_sendmidi_errors():
  sender = FakeSender()
  os.write(sender._err_w, b"Couldn't find MIDI output port\n")
  assert "Couldn't find MIDI output" in serial_stall.send(sender, 0)


def test_send_reports_sendmidi_exit():
  assert serial_stall.send(FakeSender(returncode=1), 0) == "sendmidi exited rc=1"
