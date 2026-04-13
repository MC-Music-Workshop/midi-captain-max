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


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_button_count_matches_device(config_path):
  config = load(config_path)
  device = config.get("device", "std10")
  expected = DEVICE_BUTTON_COUNT[device]
  actual = len(config["buttons"])
  assert actual == expected, (
    f"{config_path.name}: device={device} expects {expected} buttons, got {actual}"
  )


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_encoder_only_on_supported_devices(config_path):
  config = load(config_path)
  device = config.get("device", "std10")
  if "encoder" in config and device not in DEVICES_WITH_ENCODER:
    pytest.fail(f"{config_path.name}: device={device} does not support encoder")


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_expression_only_on_supported_devices(config_path):
  config = load(config_path)
  device = config.get("device", "std10")
  if "expression" in config and device not in DEVICES_WITH_EXPRESSION:
    pytest.fail(f"{config_path.name}: device={device} does not support expression")


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_encoder_min_max_initial(config_path):
  config = load(config_path)
  enc = config.get("encoder")
  if enc is None:
    return
  enc_min = enc.get("min", 0)
  enc_max = enc.get("max", 127)
  enc_initial = enc.get("initial", 64)
  assert enc_max >= enc_min, f"{config_path.name}: encoder max {enc_max} < min {enc_min}"
  assert enc_min <= enc_initial <= enc_max, (
    f"{config_path.name}: encoder initial {enc_initial} not in [{enc_min}, {enc_max}]"
  )


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_expression_min_max(config_path):
  config = load(config_path)
  exp = config.get("expression")
  if exp is None:
    return
  for pedal in ("exp1", "exp2"):
    p = exp[pedal]
    p_min = p.get("min", 0)
    p_max = p.get("max", 127)
    assert p_max >= p_min, (
      f"{config_path.name}: {pedal} max {p_max} < min {p_min}"
    )


@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_states_length_matches_keytimes(config_path):
  """When `states` is present, its length should match `keytimes`."""
  config = load(config_path)
  for i, btn in enumerate(config["buttons"]):
    states = btn.get("states")
    if states is None:
      continue
    keytimes = btn.get("keytimes", 1)
    assert len(states) == keytimes, (
      f"{config_path.name}: button {i} has keytimes={keytimes} "
      f"but {len(states)} states"
    )
