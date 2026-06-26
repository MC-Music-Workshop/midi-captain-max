"""
Cross-field validation tests for shipped configs.

These rules can't be expressed in JSON Schema (they involve relationships
between fields), but they're enforced by Rust validation in the editor.
Verifying that shipped configs satisfy them catches drift between editor
output and what the firmware actually expects.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
CONFIG_DIR = REPO_ROOT / "firmware" / "dev"

DEVICE_BUTTON_COUNT = {
  "std10": 10,
  "mini6": 6,
  "nano4": 4,
  "duo2": 2,
  "one1": 1,
}

DEVICES_WITH_ENCODER = {"std10"}
DEVICES_WITH_EXPRESSION = {"std10"}


def config_files():
  return sorted(CONFIG_DIR.glob("config*.json"))


def load(path: Path) -> dict:
  with open(path) as f:
    return json.load(f)


def pages(config: dict) -> list:
  """Pages in a config. Control-surface data (buttons/encoder/expression) lives
  per-page since #15, so cross-field rules are checked per page."""
  return config.get("pages", [])


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_button_count_matches_device(config_path):
  config = load(config_path)
  device = config.get("device", "std10")
  expected = DEVICE_BUTTON_COUNT[device]
  for pi, page in enumerate(pages(config)):
    actual = len(page["buttons"])
    assert actual == expected, (
      f"{config_path.name} page {pi}: device={device} expects {expected} buttons, got {actual}"
    )


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_encoder_only_on_supported_devices(config_path):
  config = load(config_path)
  device = config.get("device", "std10")
  for pi, page in enumerate(pages(config)):
    if "encoder" in page and device not in DEVICES_WITH_ENCODER:
      pytest.fail(f"{config_path.name} page {pi}: device={device} does not support encoder")


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_expression_only_on_supported_devices(config_path):
  config = load(config_path)
  device = config.get("device", "std10")
  for pi, page in enumerate(pages(config)):
    if "expression" in page and device not in DEVICES_WITH_EXPRESSION:
      pytest.fail(f"{config_path.name} page {pi}: device={device} does not support expression")


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_encoder_min_max_initial(config_path):
  config = load(config_path)
  for pi, page in enumerate(pages(config)):
    enc = page.get("encoder")
    if enc is None:
      continue
    enc_min = enc.get("min", 0)
    enc_max = enc.get("max", 127)
    enc_initial = enc.get("initial", 64)
    assert enc_max >= enc_min, f"{config_path.name} page {pi}: encoder max {enc_max} < min {enc_min}"
    assert enc_min <= enc_initial <= enc_max, (
      f"{config_path.name} page {pi}: encoder initial {enc_initial} not in [{enc_min}, {enc_max}]"
    )


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_expression_min_max(config_path):
  config = load(config_path)
  for pi, page in enumerate(pages(config)):
    exp = page.get("expression")
    if exp is None:
      continue
    for pedal in ("exp1", "exp2"):
      p = exp[pedal]
      p_min = p.get("min", 0)
      p_max = p.get("max", 127)
      assert p_max >= p_min, (
        f"{config_path.name} page {pi}: {pedal} max {p_max} < min {p_min}"
      )


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_states_length_matches_keytimes(config_path):
  """When `states` is present, its length should match `keytimes`."""
  config = load(config_path)
  for pi, page in enumerate(pages(config)):
    for i, btn in enumerate(page["buttons"]):
      states = btn.get("states")
      if states is None:
        continue
      keytimes = btn.get("keytimes", 1)
      assert len(states) == keytimes, (
        f"{config_path.name} page {pi}: button {i} has keytimes={keytimes} "
        f"but {len(states)} states"
      )
