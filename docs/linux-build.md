# Linux Build Documentation

This document describes the Linux build and GPG signing configuration for the
MIDI Captain MAX Config Editor.

## Overview

The Config Editor is built for Linux using the same stack as macOS/Windows
(Tauri 2 + SvelteKit + Rust). The Linux job produces two distributable formats:

1. **AppImage** — a single portable executable that runs on most distributions
   without installation.
2. **deb** — a Debian/Ubuntu package for users who prefer their package manager.

`.rpm` is intentionally not built (the Ubuntu runner has no `rpmbuild` toolchain
and the AppImage already covers RPM-based distros).

Each artifact is signed with a **detached GPG signature** (`.asc`), matching the
Linux signing mechanism used in
[`boomerang-plugin`](https://github.com/MC-Music-Workshop/boomerang-plugin/blob/main/.github/workflows/build.yml).

## Build Configuration

### Runner

The build runs on **`ubuntu-22.04`**, not `ubuntu-latest`. The AppImage and deb
link against the runner's `glibc`; building on the oldest supported runner keeps
the artifacts runnable on the widest range of user distros. Newer runners would
raise the minimum `glibc` and break on older systems.

### System dependencies

Tauri 2 needs the WebKitGTK 4.1 stack and bundler tooling; the `serialport`
crate needs `libudev-dev`; the AppImage bundler runs `linuxdeploy` (itself an
AppImage), which needs `libfuse2` on the FUSE-less runner:

```bash
sudo apt-get install -y \
  libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev \
  librsvg2-dev libxdo-dev libssl-dev libudev-dev libfuse2 \
  file build-essential curl wget
```

The build step also sets `APPIMAGE_EXTRACT_AND_RUN=1` so the bundler's
`linuxdeploy` AppImage runs by extraction instead of via FUSE.

### Bundle selection

```bash
npm run tauri build -- --bundles appimage,deb
```

## GPG Signing

### Secrets

Configured as repository secrets (shared with `boomerang-plugin`'s naming):

| Secret | Contents |
|--------|----------|
| `GPG_PRIVATE_KEY` | ASCII-armored private signing key (`gpg --armor --export-secret-keys`) |
| `GPG_PASSPHRASE` | Passphrase that unlocks the key |

If `GPG_PRIVATE_KEY` is unset, the build still succeeds and uploads **unsigned**
artifacts (a CI warning is emitted) — exactly how the macOS job degrades without
a signing certificate.

### Generating a signing key

```bash
# 1. Generate a key (choose a name/email for the project identity)
gpg --full-generate-key

# 2. Find the key id
gpg --list-secret-keys --keyid-format=long

# 3. Export the private key (ASCII-armored) for the GPG_PRIVATE_KEY secret
gpg --armor --export-secret-keys <KEY_ID>

# 4. Export the PUBLIC key so users can verify signatures
gpg --armor --export <KEY_ID> > midi-captain-max-public.asc
```

Paste the output of step 3 into the `GPG_PRIVATE_KEY` secret and the key's
passphrase into `GPG_PASSPHRASE`. Publish the public key (step 4) so users can
verify downloads.

### How CI signs

For each built artifact:

```bash
echo "$GPG_PASSPHRASE" | gpg --batch --yes --passphrase-fd 0 \
  --pinentry-mode loopback --armor --detach-sign \
  --output "${artifact}.asc" "$artifact"

gpg --verify "${artifact}.asc" "$artifact"   # fails the build if not "Good signature"
```

The signature is over the file **contents**, so `release.yml` can rename both
the artifact and its `.asc` to friendly names without invalidating verification.

### How users verify

```bash
# Import the project public key once
gpg --import midi-captain-max-public.asc

# Verify a download
gpg --verify MIDI-Captain-MAX-Config-Editor-<version>.AppImage.asc \
            MIDI-Captain-MAX-Config-Editor-<version>.AppImage
# Look for: "Good signature from ..."
```

## Build Artifacts

### AppImage

**Filename format:** `MIDI-Captain-MAX-Config-Editor-{version}.AppImage`

```bash
chmod +x MIDI-Captain-MAX-Config-Editor-<version>.AppImage
./MIDI-Captain-MAX-Config-Editor-<version>.AppImage
```

### deb

**Filename format:** `MIDI-Captain-MAX-Config-Editor-{version}.deb`

```bash
sudo apt install ./MIDI-Captain-MAX-Config-Editor-<version>.deb
# or
sudo dpkg -i MIDI-Captain-MAX-Config-Editor-<version>.deb
```

## Troubleshooting

### AppImage fails to bundle (FUSE error)

Ensure `libfuse2` is installed and `APPIMAGE_EXTRACT_AND_RUN=1` is set on the
build step (both are configured in CI).

### `webkit2gtk-4.1` not found

Tauri 2 requires the 4.1 (not 4.0) WebKitGTK package. It is available on Ubuntu
22.04+ as `libwebkit2gtk-4.1-dev`.

### AppImage won't start on an older distro

The build runner's `glibc` is newer than the target system. Keep the build on
`ubuntu-22.04`; do not bump to `ubuntu-latest`.

## Local Development (Linux)

```bash
# Install deps (Debian/Ubuntu)
sudo apt-get install -y \
  libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev \
  librsvg2-dev libxdo-dev libssl-dev libudev-dev libfuse2 \
  file build-essential curl wget

cd config-editor
npm install
npm run tauri build -- --bundles appimage,deb

# Output in:
# src-tauri/target/release/bundle/appimage/
# src-tauri/target/release/bundle/deb/
```

## Cross-Platform Build Matrix

| Platform | Runner | Artifacts |
|----------|--------|-----------|
| macOS | `macos-latest` | `.dmg`, `.app` (signed + notarized) |
| Windows | `windows-latest` | `.msi`, `-setup.exe` (unsigned) |
| Linux | `ubuntu-22.04` | `.AppImage`, `.deb` (GPG detached `.asc`) |

## Resources

- [Tauri Linux Bundle Docs](https://tauri.app/distribute/)
- [AppImage Documentation](https://docs.appimage.org/)
- [GnuPG Detached Signatures](https://www.gnupg.org/gph/en/manual/x135.html)
