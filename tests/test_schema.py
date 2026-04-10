"""
Tests for config.schema.json validation.

Verifies that:
- All shipped config files pass the schema
- The schema correctly rejects invalid configs
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "config.schema.json"
CONFIG_DIR = REPO_ROOT / "firmware" / "dev"


@pytest.fixture(scope="module")
def schema():
  with open(SCHEMA_PATH) as f:
    return json.load(f)


@pytest.fixture(scope="module")
def validator(schema):
  Draft7Validator.check_schema(schema)
  return Draft7Validator(schema)


def config_files():
  """Discover all config*.json files in firmware/dev/."""
  return sorted(CONFIG_DIR.glob("config*.json"))


# --- Positive tests: all shipped configs must pass ---

@pytest.mark.parametrize("config_path", config_files(), ids=lambda p: p.name)
def test_config_file_valid(validator, config_path):
  with open(config_path) as f:
    config = json.load(f)
  errors = list(validator.iter_errors(config))
  assert errors == [], f"{config_path.name}: {errors[0].message}"


def test_schema_is_valid_draft7(schema):
  """The schema itself must be valid JSON Schema draft-07."""
  Draft7Validator.check_schema(schema)


# --- Negative tests: schema must reject bad input ---

class TestRejectsInvalidLabel:
  def test_label_too_long(self, validator):
    config = {"buttons": [{"label": "TOOLONG!", "color": "red"}]}
    errors = [e for e in validator.iter_errors(config) if e.validator == "maxLength"]
    assert len(errors) > 0

  def test_label_invalid_chars(self, validator):
    config = {"buttons": [{"label": "A/B", "color": "red"}]}
    errors = [e for e in validator.iter_errors(config) if e.validator == "pattern"]
    assert len(errors) > 0


class TestRejectsInvalidEnums:
  def test_invalid_color(self, validator):
    config = {"buttons": [{"label": "OK", "color": "nope"}]}
    assert not validator.is_valid(config)

  def test_invalid_message_type(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "type": "sysex"}]}
    assert not validator.is_valid(config)

  def test_invalid_mode(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "mode": "latch"}]}
    assert not validator.is_valid(config)

  def test_invalid_off_mode(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "off_mode": "blink"}]}
    assert not validator.is_valid(config)


class TestRejectsOutOfRange:
  def test_cc_over_127(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "cc": 200}]}
    assert not validator.is_valid(config)

  def test_channel_over_15(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "channel": 16}]}
    assert not validator.is_valid(config)

  def test_keytimes_over_99(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "keytimes": 100}]}
    assert not validator.is_valid(config)

  def test_keytimes_zero(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "keytimes": 0}]}
    assert not validator.is_valid(config)

  def test_flash_ms_too_low(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "flash_ms": 10}]}
    assert not validator.is_valid(config)

  def test_flash_ms_too_high(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "flash_ms": 9999}]}
    assert not validator.is_valid(config)

  def test_pc_step_zero(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "pc_step": 0}]}
    assert not validator.is_valid(config)

  def test_negative_cc(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "cc": -1}]}
    assert not validator.is_valid(config)


class TestRejectsAdditionalProperties:
  def test_extra_top_level_field(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red"}], "bogus": True}
    assert not validator.is_valid(config)

  def test_extra_button_field(self, validator):
    config = {"buttons": [{"label": "OK", "color": "red", "unknown": 42}]}
    assert not validator.is_valid(config)


class TestRejectsMissingRequired:
  def test_missing_buttons(self, validator):
    config = {"device": "std10"}
    assert not validator.is_valid(config)

  def test_missing_button_label(self, validator):
    config = {"buttons": [{"color": "red"}]}
    assert not validator.is_valid(config)

  def test_missing_button_color(self, validator):
    config = {"buttons": [{"label": "OK"}]}
    assert not validator.is_valid(config)


class TestEncoderValidation:
  def test_valid_encoder(self, validator):
    config = {
      "buttons": [{"label": "OK", "color": "red"}],
      "encoder": {"enabled": True, "cc": 11, "label": "ENC"},
    }
    assert validator.is_valid(config)

  def test_encoder_label_too_long(self, validator):
    config = {
      "buttons": [{"label": "OK", "color": "red"}],
      "encoder": {"enabled": True, "cc": 11, "label": "WAYTOOLONG"},
    }
    assert not validator.is_valid(config)

  def test_encoder_push_extra_field(self, validator):
    config = {
      "buttons": [{"label": "OK", "color": "red"}],
      "encoder": {
        "enabled": True, "cc": 11, "label": "ENC",
        "push": {"enabled": True, "cc": 14, "label": "P", "bogus": 1},
      },
    }
    assert not validator.is_valid(config)


class TestExpressionValidation:
  def test_valid_expression(self, validator):
    config = {
      "buttons": [{"label": "OK", "color": "red"}],
      "expression": {
        "exp1": {"enabled": True, "cc": 12, "label": "EXP1"},
        "exp2": {"enabled": True, "cc": 13, "label": "EXP2"},
      },
    }
    assert validator.is_valid(config)

  def test_invalid_polarity(self, validator):
    config = {
      "buttons": [{"label": "OK", "color": "red"}],
      "expression": {
        "exp1": {"enabled": True, "cc": 12, "label": "EXP1", "polarity": "backwards"},
        "exp2": {"enabled": True, "cc": 13, "label": "EXP2"},
      },
    }
    assert not validator.is_valid(config)
