"""Tests for tools/make-update-manifest.py, the in-app update manifest (#18)."""

import base64
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
  "make_update_manifest", REPO_ROOT / "tools" / "make-update-manifest.py"
)
manifest_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(manifest_tool)

TAG = "v1.15.0-beta.3"
REPO = "MC-Music-Workshop/midi-captain-max"
NOW = datetime(2026, 11, 12, 18, 30, tzinfo=timezone.utc)


def fake_sig(label, version=None):
  """A Tauri updater .sig: base64 of a minisign signature file. `label` stands in for the key material."""
  comment = "timestamp:1794512333\tfile:app"
  if version:
    comment += f"\tversion:{version}"
  text = f"untrusted comment: {label}\nRWQ{label}\ntrusted comment: {comment}\nglobal\n"
  return base64.b64encode(text.encode()).decode()


def sign(sigs, suffix, label="sig", version=None):
  signature = fake_sig(label, version)
  (sigs / f"MIDI-Captain-MAX-Config-Editor-{TAG}{suffix}.sig").write_text(signature + "\n")
  return signature


def test_no_signatures_means_no_manifest(tmp_path):
  assert manifest_tool.build_manifest(TAG, REPO, tmp_path, NOW) is None


def test_mac_archive_serves_both_architectures(tmp_path):
  signature = sign(tmp_path, ".app.tar.gz", "macsig")
  m = manifest_tool.build_manifest(TAG, REPO, tmp_path, NOW)
  url = f"https://github.com/{REPO}/releases/download/{TAG}/MIDI-Captain-MAX-Config-Editor-{TAG}.app.tar.gz"
  assert m["platforms"]["darwin-aarch64"] == {"url": url, "signature": signature}
  assert m["platforms"]["darwin-x86_64"] == m["platforms"]["darwin-aarch64"]


def test_each_installer_type_gets_its_own_key(tmp_path):
  sigs = {suffix: sign(tmp_path, suffix, f"key{i}") for i, suffix in enumerate(manifest_tool.PLATFORMS)}
  p = manifest_tool.build_manifest(TAG, REPO, tmp_path, NOW)["platforms"]
  assert p["windows-x86_64-msi"]["signature"] == sigs[".msi"]
  assert p["windows-x86_64-nsis"]["signature"] == sigs["-setup.exe"]
  assert p["windows-x86_64"]["signature"] == sigs["-setup.exe"]
  assert p["linux-x86_64-deb"]["signature"] == sigs["_amd64.deb"]
  assert p["linux-x86_64"]["signature"] == sigs["_amd64.AppImage"]
  assert p["linux-aarch64"]["signature"] == sigs["_arm64.AppImage"]


def test_unsigned_installers_are_left_out(tmp_path):
  sign(tmp_path, "-setup.exe")
  p = manifest_tool.build_manifest(TAG, REPO, tmp_path, NOW)["platforms"]
  assert "darwin-aarch64" not in p
  assert "windows-x86_64-msi" not in p


def test_version_and_metadata(tmp_path):
  sign(tmp_path, ".msi")
  m = manifest_tool.build_manifest(TAG, REPO, tmp_path, NOW)
  assert m["version"] == "1.15.0-beta.3"
  assert m["pub_date"] == "2026-11-12T18:30:00Z"
  assert m["notes"].endswith(f"/releases/tag/{TAG}")


def test_main_writes_json(tmp_path):
  sigs = tmp_path / "sigs"
  sigs.mkdir()
  signature = sign(sigs, ".msi")
  out = tmp_path / "latest.json"
  assert manifest_tool.main(["--tag", TAG, "--repo", REPO, "--sigs", str(sigs), "--out", str(out)]) == 0
  assert json.loads(out.read_text())["platforms"]["windows-x86_64-msi"]["signature"] == signature


def test_signature_for_the_announced_version_is_accepted(tmp_path):
  sign(tmp_path, "-setup.exe", version="v1.15.0-beta.3")
  assert manifest_tool.build_manifest(TAG, REPO, tmp_path, NOW) is not None


def test_signature_for_a_wix_mangled_version_fails_the_release(tmp_path):
  # The updater would reject this as SignedVersionMismatch on every Windows install.
  sign(tmp_path, "-setup.exe", version="1.15.0-3")
  with pytest.raises(ValueError, match="signed for version 1.15.0-3"):
    manifest_tool.build_manifest(TAG, REPO, tmp_path, NOW)
