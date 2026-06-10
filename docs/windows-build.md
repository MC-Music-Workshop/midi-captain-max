# Windows Build Documentation

This document describes the Windows build configuration for the MIDI Captain MAX Config Editor.

## Overview

The Config Editor is built for Windows using:
- **Tauri 2.x** — Cross-platform native app framework
- **SvelteKit** — Frontend framework
- **Rust** — Backend runtime

The build produces two Windows installers:
1. **MSI** — Traditional Windows Installer package
2. **NSIS** — Nullsoft Scriptable Install System (modern installer)

## Build Configuration

### Tauri Configuration

File: `config-editor/src-tauri/tauri.conf.json`

```json
{
  "bundle": {
    "active": true,
    "targets": "all",
    "windows": {
      "certificateThumbprint": null,
      "digestAlgorithm": "sha256"
    }
  }
}
```

**Key settings:**
- `targets: "all"` — Build all supported formats for the current platform
- `certificateThumbprint: null` — No code signing certificate configured (unsigned builds)
- `digestAlgorithm: "sha256"` — Hash algorithm for file integrity

### CI Workflow

File: `.github/workflows/ci.yml`

```yaml
build-config-editor-windows:
  name: Build Config Editor (Windows)
  runs-on: windows-latest
  timeout-minutes: 30
  needs: lint
  steps:
    - uses: actions/checkout@v6
    - name: Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '20'
    - name: Setup Rust
      uses: dtolnay/rust-toolchain@stable
    - name: Install frontend dependencies
      run: |
        cd config-editor
        npm install
    - name: Build Tauri app
      run: |
        cd config-editor
        npm run tauri build
        Get-ChildItem -Path src-tauri\target\release\bundle\ -Recurse
    - name: Upload MSI artifact
      uses: actions/upload-artifact@v7
      with:
        name: config-editor-msi
        path: config-editor/src-tauri/target/release/bundle/msi/*.msi
        retention-days: 90
    - name: Upload NSIS artifact
      uses: actions/upload-artifact@v7
      with:
        name: config-editor-nsis
        path: config-editor/src-tauri/target/release/bundle/nsis/*.exe
        retention-days: 90
```

**Build process:**
1. Checkout repository
2. Setup Node.js 20
3. Setup latest stable Rust toolchain
4. Install npm dependencies
5. Run `npm run tauri build` (builds both MSI and NSIS)
6. Upload artifacts to GitHub Actions

### Release Workflow

File: `.github/workflows/release.yml`

The release workflow downloads Windows artifacts from CI and renames them:

```bash
# Find and rename config editor MSI (Windows)
MSI_FILE=$(find ci-artifacts -name "*.msi" | head -1)
if [ -n "$MSI_FILE" ]; then
  cp "$MSI_FILE" "dist/MIDI-Captain-MAX-Config-Editor-${VERSION}.msi"
fi

# Find and rename config editor NSIS installer (Windows)
NSIS_FILE=$(find ci-artifacts -name "*-setup.exe" | head -1)
if [ -n "$NSIS_FILE" ]; then
  cp "$NSIS_FILE" "dist/MIDI-Captain-MAX-Config-Editor-${VERSION}-setup.exe"
fi
```

## Build Artifacts

### MSI Installer

**Filename format:** `MIDI-Captain-MAX-Config-Editor-{version}.msi`

**Features:**
- Traditional Windows Installer
- Supports silent installation: `msiexec /i installer.msi /quiet`
- Automatic uninstaller in Windows Settings
- Can be deployed via Group Policy

**Usage:**
```powershell
# Interactive install
.\MIDI-Captain-MAX-Config-Editor-v1.0.0.msi

# Silent install
msiexec /i MIDI-Captain-MAX-Config-Editor-v1.0.0.msi /quiet

# Uninstall
msiexec /x MIDI-Captain-MAX-Config-Editor-v1.0.0.msi /quiet
```

### NSIS Installer

**Filename format:** `MIDI-Captain-MAX-Config-Editor-{version}-setup.exe`

**Features:**
- Modern installer with GUI wizard
- Smaller file size than MSI
- Custom branding and license display
- Start Menu shortcuts

**Usage:**
```powershell
# Interactive install
.\MIDI-Captain-MAX-Config-Editor-v1.0.0-setup.exe

# Silent install
.\MIDI-Captain-MAX-Config-Editor-v1.0.0-setup.exe /S

# Uninstall (via Control Panel or uninstaller)
```

## Code Signing

**Current status:** Windows builds are **unsigned**.

Windows will show a SmartScreen warning when running unsigned installers:
- "Windows protected your PC"
- Click "More info" → "Run anyway"

### Future: Code Signing Setup

To sign Windows builds, configure:

1. **Acquire a code signing certificate:**
   - Extended Validation (EV) certificate recommended
   - From CA like DigiCert, Sectigo, or GlobalSign
   - Cost: ~$300-500/year

2. **Add GitHub secrets:**
   - `WINDOWS_CERTIFICATE` — Base64-encoded PFX file
   - `WINDOWS_CERTIFICATE_PASSWORD` — PFX password

3. **Update workflow:**
   ```yaml
   - name: Import code signing certificate
     shell: pwsh
     run: |
       $pfx = [Convert]::FromBase64String("${{ secrets.WINDOWS_CERTIFICATE }}")
       [IO.File]::WriteAllBytes("$pwd\cert.pfx", $pfx)
       # Certificate will be automatically used by Tauri build
   ```

4. **Update tauri.conf.json:**
   ```json
   "windows": {
     "certificateThumbprint": "<cert-thumbprint>",
     "timestampUrl": "http://timestamp.digicert.com"
   }
   ```

## Troubleshooting

### "Rust not found" error
- Ensure `rust-toolchain@stable` action runs before build
- Check Windows runner has Rust in PATH

### "MSI not found" after build
- Verify Tauri built successfully (check logs)
- Ensure `targets: "all"` is set in tauri.conf.json
- Check artifact upload path matches actual output path

### SmartScreen warnings for users
- Expected for unsigned builds
- Users can bypass: "More info" → "Run anyway"
- To remove: implement code signing (see above)

## Local Development (Windows)

To build locally on Windows:

```powershell
# Prerequisites
choco install nodejs rust

# Clone and build
git clone https://github.com/MC-Music-Workshop/midi-captain-max.git
cd midi-captain-max/config-editor
npm install
npm run tauri build

# Output in:
# src-tauri\target\release\bundle\msi\
# src-tauri\target\release\bundle\nsis\
```

## Cross-Platform Build Matrix

| Platform | Runner | Build Time | Artifacts |
|----------|--------|------------|-----------|
| macOS | `macos-latest` | ~15 min | `.dmg`, `.app` |
| Windows | `windows-latest` | ~20 min | `.msi`, `-setup.exe` |
| Linux amd64 | `ubuntu-22.04` | ~15 min | `.AppImage`, `.deb` (GPG-signed) — see `docs/linux-build.md` |
| Linux arm64 | `ubuntu-22.04-arm` | ~15 min | `.AppImage`, `.deb` (GPG-signed) — see `docs/linux-build.md` |

## Resources

- [Tauri Windows Bundle Docs](https://tauri.app/v2/guides/distribution/windows)
- [NSIS Documentation](https://nsis.sourceforge.io/Docs/)
- [Windows Code Signing](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
