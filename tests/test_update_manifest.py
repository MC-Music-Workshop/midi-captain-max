"""Tests for tools/make-update-manifest.py, the in-app update manifest (#18)."""

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
  "make_update_manifest", REPO_ROOT / "tools" / "make-update-manifest.py"
)
manifest_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(manifest_tool)

TAG = "v1.15.0-beta.3"
REPO = "MC-Music-Workshop/midi-captain-max"
NOW = datetime(2026, 11, 12, 18, 30, tzinfo=timezone.utc)


def sign(sigs, suffix, signature="sig"):
  (sigs / f"MIDI-Captain-MAX-Config-Editor-{TAG}{suffix}.sig").write_text(signature + "\n")


def test_no_signatures_means_no_manifest(tmp_path):
  assert manifest_tool.build_manifest(TAG, REPO, tmp_path, NOW) is None


def test_mac_archive_serves_both_architectures(tmp_path):
  sign(tmp_path, ".app.tar.gz", "macsig")
  m = manifest_tool.build_manifest(TAG, REPO, tmp_path, NOW)
  url = f"https://github.com/{REPO}/releases/download/{TAG}/MIDI-Captain-MAX-Config-Editor-{TAG}.app.tar.gz"
  assert m["platforms"]["darwin-aarch64"] == {"url": url, "signature": "macsig"}
  assert m["platforms"]["darwin-x86_64"] == m["platforms"]["darwin-aarch64"]


def test_each_installer_type_gets_its_own_key(tmp_path):
  for suffix in manifest_tool.PLATFORMS:
    sign(tmp_path, suffix, suffix)
  p = manifest_tool.build_manifest(TAG, REPO, tmp_path, NOW)["platforms"]
  assert p["windows-x86_64-msi"]["signature"] == ".msi"
  assert p["windows-x86_64-nsis"]["signature"] == "-setup.exe"
  assert p["windows-x86_64"]["signature"] == "-setup.exe"
  assert p["linux-x86_64-deb"]["signature"] == "_amd64.deb"
  assert p["linux-x86_64"]["signature"] == "_amd64.AppImage"
  assert p["linux-aarch64"]["signature"] == "_arm64.AppImage"


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
  sign(sigs, ".msi")
  out = tmp_path / "latest.json"
  assert manifest_tool.main(["--tag", TAG, "--repo", REPO, "--sigs", str(sigs), "--out", str(out)]) == 0
  assert json.loads(out.read_text())["platforms"]["windows-x86_64-msi"]["signature"] == "sig"
