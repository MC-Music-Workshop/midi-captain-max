"""
Drift test: every field name read by firmware/dev/core/config.py must be defined
in config.schema.json.

If the firmware looks up a field name that the schema doesn't know about, the
editor will never write it and the firmware will silently fall back to defaults.
This test catches that class of bug at the source.
"""

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "config.schema.json"
CONFIG_PY = REPO_ROOT / "firmware" / "dev" / "core" / "config.py"

# Field names read in config.py that aren't config keys — exclude from drift check.
# (Empty for now; populate if config.py ever uses .get() on non-config dicts.)
NON_CONFIG_KEYS: set[str] = set()


def extract_get_keys(source: str) -> set[str]:
  """Find every string literal used as the first arg to a .get() call."""
  tree = ast.parse(source)
  keys: set[str] = set()
  for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
      continue
    if not isinstance(node.func, ast.Attribute):
      continue
    if node.func.attr != "get":
      continue
    if not node.args:
      continue
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
      keys.add(first.value)
  return keys


def collect_schema_field_names(schema: dict) -> set[str]:
  """Walk schema and collect every property name defined under 'properties'."""
  names: set[str] = set()

  def walk(node):
    if isinstance(node, dict):
      props = node.get("properties")
      if isinstance(props, dict):
        names.update(props.keys())
      for v in node.values():
        walk(v)
    elif isinstance(node, list):
      for v in node:
        walk(v)

  walk(schema)
  return names


@pytest.fixture(scope="module")
def schema_fields() -> set[str]:
  with open(SCHEMA_PATH) as f:
    schema = json.load(f)
  return collect_schema_field_names(schema)


@pytest.fixture(scope="module")
def firmware_keys() -> set[str]:
  source = CONFIG_PY.read_text()
  return extract_get_keys(source) - NON_CONFIG_KEYS


def test_firmware_reads_only_schema_defined_fields(firmware_keys, schema_fields):
  """Every key the firmware reads must be defined in the schema."""
  missing = firmware_keys - schema_fields
  assert not missing, (
    f"Firmware reads fields not defined in config.schema.json: {sorted(missing)}\n"
    f"Either add them to the schema or remove the .get() calls from config.py."
  )


def test_state_override_fields_match_schema(schema_fields):
  """The STATE_OVERRIDE_FIELDS tuple in config.py must match the schema's StateOverride."""
  with open(SCHEMA_PATH) as f:
    schema = json.load(f)
  state_props = set(schema["definitions"]["StateOverride"]["properties"].keys())

  # Import the firmware constant
  import sys
  sys.path.insert(0, str(REPO_ROOT / "firmware" / "dev"))
  from core.config import STATE_OVERRIDE_FIELDS
  firmware_state_fields = set(STATE_OVERRIDE_FIELDS)

  assert firmware_state_fields == state_props, (
    f"STATE_OVERRIDE_FIELDS in config.py does not match schema StateOverride.\n"
    f"  Only in firmware: {firmware_state_fields - state_props}\n"
    f"  Only in schema:   {state_props - firmware_state_fields}"
  )


def test_valid_message_types_match_schema():
  """The VALID_TYPES tuple in config.py must match the schema's MessageType enum."""
  with open(SCHEMA_PATH) as f:
    schema = json.load(f)
  schema_types = set(schema["definitions"]["MessageType"]["enum"])

  import sys
  sys.path.insert(0, str(REPO_ROOT / "firmware" / "dev"))
  from core.config import VALID_TYPES
  firmware_types = set(VALID_TYPES)

  assert firmware_types == schema_types, (
    f"VALID_TYPES in config.py does not match schema MessageType enum.\n"
    f"  Only in firmware: {firmware_types - schema_types}\n"
    f"  Only in schema:   {schema_types - firmware_types}"
  )
