# Plan: arm64 Linux build for the Config Editor

**Status:** Not started — saved for future implementation.
**Tracking issue:** #149.
**Branch:** `linux` (worktree at `.worktrees/linux`).
**Follows:** #26 (amd64 Linux build + GPG signing, merged in #148).

## Goal

Add an `aarch64` (arm64) Linux build alongside the existing amd64 Linux job, so
the Config Editor ships for ARM Linux desktops (Raspberry Pi 4/5 64-bit, Asahi
Linux, ARM Chromebooks/Crostini, Ampere workstations) and can be tested in a
fast native UTM VM on Apple Silicon Macs.

GitHub provides free arm64 Linux runners for **public** repos
(`ubuntu-22.04-arm`), so this is a native build — no cross-compilation.

## Why now / why low cost

- The amd64 build already exists; arm64 is a matrix leg, not new logic.
- Runs concurrently with amd64 → no wall-clock hit (~15 min each, parallel).
- Adds 2 release assets (`*_arm64.AppImage` + `.deb`) plus their `.asc`.
- Caveat: free arm64 runners apply to **public** repos only. If the repo ever
  goes private, arm64 hosted runners bill minutes.

## Must-fix issues this introduces

These are the review findings from #148 — the current single-arch code breaks
when a second arch is added, so the matrix change MUST fix them together:

1. **Artifact-name collision.** `ci.yml` uploads fixed names
   `config-editor-appimage` / `config-editor-deb`. Two matrix legs uploading the
   same name collide (`upload-artifact@v7` errors / overwrites). Suffix with the
   arch: `config-editor-appimage-${{ matrix.arch }}` etc.
2. **`release.yml` drops an arch.** It currently does
   `find ci-artifacts -name "*.AppImage" | head -1` (and the same for `.deb`),
   which silently keeps only one arch. Replace `head -1` with a loop over both
   arches, emitting arch-suffixed friendly names.

## Implementation steps

### 1. `ci.yml` — convert `build-config-editor-linux` to a matrix

How:

```yaml
build-config-editor-linux:
  name: Build Config Editor (Linux ${{ matrix.arch }})
  strategy:
    fail-fast: false   # one arch failing shouldn't kill the other
    matrix:
      include:
        - { runner: ubuntu-22.04,     arch: amd64 }
        - { runner: ubuntu-22.04-arm, arch: arm64 }
  runs-on: ${{ matrix.runner }}
  timeout-minutes: 30
  needs: [lint, build-zip]
  ...
```

- Keep all existing steps (system deps, GPG import, sign, summary) unchanged —
  they are arch-agnostic. `dtolnay/rust-toolchain@stable` picks the host target
  automatically on the arm64 runner; do **not** hardcode a `--target`.
- Suffix both upload artifact names with `-${{ matrix.arch }}`:
  - `config-editor-appimage-${{ matrix.arch }}`
  - `config-editor-deb-${{ matrix.arch }}`
- The build/sign output paths (`bundle/appimage`, `bundle/deb`) are identical
  per arch — no change needed there; Tauri stamps the arch into the *filename*
  (`..._amd64.AppImage` vs `..._arm64.AppImage`).

### 2. `release.yml` — loop over arches instead of `head -1`

How (replace the AppImage/deb prepare blocks):

```bash
for arch in amd64 arm64; do
  APPIMAGE_FILE=$(find ci-artifacts -name "*_${arch}.AppImage" | head -1)
  if [ -n "$APPIMAGE_FILE" ]; then
    cp "$APPIMAGE_FILE" "dist/MIDI-Captain-MAX-Config-Editor-${VERSION}_${arch}.AppImage"
    [ -f "${APPIMAGE_FILE}.asc" ] && cp "${APPIMAGE_FILE}.asc" \
      "dist/MIDI-Captain-MAX-Config-Editor-${VERSION}_${arch}.AppImage.asc"
  fi
  DEB_FILE=$(find ci-artifacts -name "*_${arch}.deb" | head -1)
  if [ -n "$DEB_FILE" ]; then
    cp "$DEB_FILE" "dist/MIDI-Captain-MAX-Config-Editor-${VERSION}_${arch}.deb"
    [ -f "${DEB_FILE}.asc" ] && cp "${DEB_FILE}.asc" \
      "dist/MIDI-Captain-MAX-Config-Editor-${VERSION}_${arch}.deb.asc"
  fi
done
```

- Tauri's amd64/arm64 filenames already carry the `_amd64` / `_arm64` token, so
  matching on `*_${arch}.AppImage` is reliable.
- The combined-bundle `for ext in ... AppImage deb asc` loop already globs by
  extension, so it picks up both arches with no change.

### 3. Docs

- `docs/linux-build.md`: add arm64 to the artifacts list and the build matrix
  table; note the public-repo arm64-runner caveat; add the Apple Silicon UTM
  native-VM testing path (UTM → Virtualize → arm64 ISO → native `*_arm64`).
- `docs/windows-build.md` cross-platform matrix: add the arm64 Linux row.
- `.github/AGENTS.md`: note the Linux job is now a 2-arch matrix and that
  artifact names are arch-suffixed (so the firmware-distribution checklist and
  release-asset expectations stay accurate).

## Verification

- `actionlint -shellcheck=` → exit 0.
- Push branch; confirm BOTH `Build Config Editor (Linux amd64)` and
  `(Linux arm64)` jobs go green and each logs `gpg: Good signature` ×2.
- Confirm 4 GUI Linux assets exist on a test release (amd64/arm64 ×
  AppImage/deb) plus 4 `.asc`.
- Smoke-test the arm64 AppImage in a UTM Virtualize arm64 VM on Apple Silicon
  (fast, native); USB-passthrough the MIDI Captain to exercise device detection.

## Open questions

- Keep `fail-fast: false`? Recommended yes — an arm64-runner hiccup shouldn't
  block the amd64 release asset.
- Worth adding arm64 to the Rust test job (`test-config-editor-rust`) too, or is
  amd64 test coverage sufficient? Default: leave tests amd64-only (logic is
  arch-independent); revisit only if an arch-specific bug appears.
