#!/usr/bin/env python3
"""Write the Config Editor's in-app update manifest (latest.json) for a release (#18).

release.yml runs this after copying the installers to dist/ under their release
asset names and their Tauri updater signatures to a sigs/ dir as <asset>.sig.
homebrew.yml later copies the manifest into the stable/beta update feeds.

Usage:
  make-update-manifest.py --tag v1.15.0 --repo OWNER/REPO --sigs sigs/ --out dist/latest.json

An installer without a signature is left out; with none at all (no signing key
in CI) no manifest is written.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ASSET_PREFIX = "MIDI-Captain-MAX-Config-Editor-"

# Release asset suffix -> updater platform keys. The plugin looks up
# "{os}-{arch}-{installer}" first, then "{os}-{arch}", so the plain key names
# the installer an install of unknown type should get.
PLATFORMS = {
  # Universal binary: both Mac architectures update from the same archive.
  ".app.tar.gz": ["darwin-aarch64", "darwin-x86_64"],
  "-setup.exe": ["windows-x86_64-nsis", "windows-x86_64"],
  ".msi": ["windows-x86_64-msi"],
  "_amd64.AppImage": ["linux-x86_64-appimage", "linux-x86_64"],
  "_amd64.deb": ["linux-x86_64-deb"],
  "_arm64.AppImage": ["linux-aarch64-appimage", "linux-aarch64"],
  "_arm64.deb": ["linux-aarch64-deb"],
}


def build_manifest(tag, repo, sigs_dir, now=None):
  """Return the manifest dict, or None when no installer has a signature."""
  base = f"https://github.com/{repo}/releases/download/{tag}/"
  platforms = {}
  for suffix, keys in PLATFORMS.items():
    asset = f"{ASSET_PREFIX}{tag}{suffix}"
    sig = Path(sigs_dir) / f"{asset}.sig"
    if not sig.is_file():
      continue
    entry = {"url": base + asset, "signature": sig.read_text().strip()}
    for key in keys:
      platforms[key] = entry
  if not platforms:
    return None
  now = now or datetime.now(timezone.utc)
  return {
    "version": tag.removeprefix("v"),
    "notes": f"https://github.com/{repo}/releases/tag/{tag}",
    "pub_date": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "platforms": platforms,
  }


def main(argv=None):
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument("--tag", required=True)
  parser.add_argument("--repo", required=True)
  parser.add_argument("--sigs", required=True)
  parser.add_argument("--out", required=True)
  args = parser.parse_args(argv)

  manifest = build_manifest(args.tag, args.repo, args.sigs)
  if manifest is None:
    print("No updater signatures found; latest.json not written.")
    return 0
  Path(args.out).write_text(json.dumps(manifest, indent=2) + "\n")
  print(f"Wrote {args.out}: {', '.join(sorted(manifest['platforms']))}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
