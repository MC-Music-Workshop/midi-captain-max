# CI/CD Agent Instructions

## Workflows

### CI (`ci.yml`) — Triggered on branch pushes AND `v*` tag pushes

- Lints with Ruff (ignores E501, F401, E402 for CircuitPython compatibility)
- Validates Python syntax + CircuitPython 7.x compatibility guard (greps for banned constructs)
- Writes `VERSION.txt` into firmware zip from `git describe`
- Runs pytest suite (`tests/`)
- Builds Config Editor for macOS, Windows, and Linux (Tauri + SvelteKit)
- Validates all `firmware/dev/config*.json` against `config.schema.json`
- Checks `types.generated.ts` is up to date

**Tag trigger is critical**: CI must run on tag push so `git describe` sees the tag and bakes the correct version into artifacts. Without this, artifacts get the pre-tag version (e.g., `1.8.0-rc1` instead of `1.8.0`).

**Docs-only PRs can't satisfy branch protection.** `ci.yml` uses `paths-ignore: ["**/*.md", "docs/**"]`, so docs-only changes run zero jobs. Branch protection's "required checks must pass" stays unreported. Merge with `gh pr merge --admin`. Long-term fix: an always-running "gate" job that short-circuits for docs-only.

**Firmware-zip artifact uses `archive: false`.** The zip payload is already compressed, so we skip GitHub's outer zip wrapper. `archive: false` ignores the `name:` input and takes the artifact name from the file's basename. Don't reintroduce `compression-level: 0` — empirically tested, it made the artifact ~10% *larger* (wrapper metadata compresses even when payload doesn't).

### Release (`release.yml`) — Triggered on `v*` tag pushes

- Downloads artifacts from the CI run for the same commit (by SHA)
- Polls for up to 30 minutes waiting for CI to complete
- Fails fast if CI fails or is cancelled
- Creates a **draft** GitHub Release with artifacts
- Auto-detects alpha/beta for pre-release flag

---

## Versioning

- **Semantic Versioning** with pre-release tags
- Tag format: `v{major}.{minor}.{patch}[-{prerelease}.{n}]`
- `VERSION.txt` is written by both `deploy.sh` and `ci.yml` from `git describe --tags --always`
- `firmware/dev/VERSION.txt` is gitignored (generated artifact)

### Version Flow

- `git describe --tags --always` → strip `v` prefix and commit-distance suffix → SEMVER
- Examples: `v1.8.0` → `1.8.0`, `v1.8.0-rc1` → `1.8.0-rc1`, `v1.5.0-11-gabc1234` → `1.5.0`
- **macOS**: uses SEMVER as-is (Tauri accepts semver pre-release identifiers)
- **Windows**: WiX MSI rejects non-numeric pre-release identifiers; conversion step strips alpha chars: `1.8.0-rc1` → `1.8.0-1`
- **Tauri v2 requires strict semver** (3-part with optional pre-release) — 4-part versions like `1.8.0.1` are rejected

### Creating a Release

```bash
git tag v1.0.0-alpha.1
git push origin v1.0.0-alpha.1
```

---

## Release Process

1. Push tag `v1.x.0` (CI must trigger on tags so version is baked in correctly)
2. CI builds artifacts with clean version
3. Release workflow creates a **draft** release — download and test artifacts
4. Publish via GitHub UI when satisfied; delete draft + tag if not

**Tauri binary versions are baked at build time.** They cannot be patched post-build due to code signing. This is why CI must run on the tag.

**Beta tags are usually unnecessary** — the draft release IS the test mechanism. Only use beta tags when you expect multiple test cycles or want a published (non-draft) beta for external testers.

**Promoting a beta to final requires re-tagging the same commit.** Tag `v1.10.0` on the same commit as `v1.10.0-beta1` and let CI rebuild — otherwise artifacts will still say `1.10.0-beta1` internally.

### Merging Release Branches

**Always use fast-forward merge** to keep the tag on main's history:
```bash
git checkout main
git merge --ff-only <branch>
git push
```
GitHub's "Rebase and merge" UI option **rewrites commit SHAs** even when a fast-forward is possible, causing the tag to point to a commit no longer on main.

---

## Artifact Flow

- **CI uploads**: `actions/upload-artifact@v7`
- **Release downloads**: `actions/download-artifact@v7`
- These are different actions — don't confuse them (easy mistake)
- Release workflow patches `/VERSION.txt` inside the firmware zip with the clean tag

---

## Deploy Scripts

`tools/deploy.sh` and `tools/deploy.ps1` share the same deploy order and progress style:
- Per-file/directory labels with `(no changes)` when nothing was updated
- Shows current firmware version on device and incoming version at start
- `sync_dir` / `sync_file` helpers (bash) wrap rsync and strip itemize-changes prefixes

All distribution paths must include the same set of files and write `VERSION.txt`. If you add a new directory under `firmware/dev/`, update **all** of these:
1. `tools/deploy.sh` — dev deploy via rsync
2. `.github/workflows/ci.yml` — firmware zip (`build-zip` job)
3. `config-editor/src-tauri/resources/firmware/` — bundled into Config Editor app (use `tools/bundle-firmware-for-dev.sh` for local dev)

**`deploy.sh` and `deploy.ps1` must stay at feature parity** — when adding device types, config files, or changing deploy logic, update both scripts.

---

## Code Signing

See [docs/macos-code-signing.md](../docs/macos-code-signing.md) for macOS setup (Team ID: `9WNXKEF4SM`) and [docs/linux-build.md](../docs/linux-build.md) for Linux GPG signing.

**Notarization 403:** Apple updated the Developer Program License Agreement — Account Holder must accept at App Store Connect, then re-run the failed CI job. No code change needed.

**Linux GPG signing** (`build-config-editor-linux`) mirrors `boomerang-plugin`: imports `GPG_PRIVATE_KEY` (ASCII-armored, not base64), detached-signs each artifact (`.asc`) with `GPG_PASSPHRASE`, then verifies. Both secrets optional — unset → unsigned build with a warning, like the macOS cert. Signatures are over file content, so `release.yml` renames artifact + `.asc` together safely.

---

## Linux CI Dependencies

`libudev-dev` required by the `serialport` crate (used by `test-config-editor-rust` and `build-config-editor-linux`).

**`build-config-editor-linux` pins `ubuntu-22.04`** (not `ubuntu-latest`): AppImage/deb link against the runner's glibc, so the oldest supported runner maximizes user-distro compatibility. Builds `--bundles appimage,deb` only (no rpm — runner has no `rpmbuild`). Needs `libwebkit2gtk-4.1-dev` + `libfuse2`, with `APPIMAGE_EXTRACT_AND_RUN=1` for the FUSE-less runner.
