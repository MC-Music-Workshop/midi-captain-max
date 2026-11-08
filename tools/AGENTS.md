# tools/ — Deploy & helper scripts

## Cross-platform parity

`deploy.sh` (POSIX) and `deploy.ps1` (Windows) MUST stay feature-equivalent. When changing one, change the other. `deploy.bat` is a launcher for `deploy.ps1`, not a third script — keep it 2 lines.

## Distribution-package layout

`ci.yml`'s `zip -j` flattens `tools/deploy.{sh,ps1,bat}` to the **root** of `midicaptain-firmware-vX.zip`. End-users run `.\deploy.ps1` (or `deploy.bat`) from the unzipped root, **not** `tools\deploy.ps1`. Keep this in mind when updating user-facing docs that reference paths.

The script handles both layouts via context auto-detection (`if (Test-Path firmware/dev)` → repo, else dist). Don't break that branch.

## PowerShell gotchas on Windows (hard to spot)

### Microsoft Store `python.exe` execution-alias shim

On Windows 10/11, `C:\Users\<u>\AppData\Local\Microsoft\WindowsApps\python.exe` is a **0-byte alias** that prints `Python was not found; run without arguments to install from the Microsoft Store` and exits non-zero. `Get-Command python` finds it; running it fails with `NativeCommandError`. Same applies to `python3.exe`, `winget`, `wt`, and other Store-aliased tools.

When detecting Python (or any Store-aliased tool) in PowerShell:
1. Reject anything whose `.Source` matches `*\WindowsApps\*`, **and**
2. Probe with `--version` and require `$LASTEXITCODE -eq 0`.

`Get-Command` alone is not sufficient. See `deploy.ps1`'s pip-resolution fallback for the working pattern (even though that path is now dead code after circup removal — it stays as defense in depth).

### `1..0` is a descending range, not empty

`$arr[1..($arr.Count - 1)]` on a **1-element array** becomes `$arr[1..0]`, and PowerShell's `1..0` evaluates to the descending range `1, 0` — which **corrupts** any "slice off the head" idiom. Use `@($arr | Select-Object -Skip 1)` instead.

### Splatting external commands

`& $cmd[0] @rest install foo` splats `$rest` as separate arguments. `& $cmd[0] $rest install foo` passes `$rest` as a single array argument. Use `@` for splat when calling external binaries with variable-length argument lists.

### Mark-of-the-Web (MOTW) blocks downloaded `.ps1`

PowerShell prompts `Do you want to run …?` on first execution of `.ps1` files downloaded from the internet (NTFS Zone.Identifier stream). `Unblock-File` clears it, but the release-friendly workaround is a `.bat` launcher invoking `powershell -NoProfile -ExecutionPolicy Bypass -File …`, which sidesteps:
- the MOTW prompt,
- any system `ExecutionPolicy` (incl. AllSigned, RemoteSigned, Restricted),

without changing user settings. This is `deploy.bat`.

Bypass is per-process, not persisted. Standard pattern used by Chocolatey, most CircuitPython tooling, etc.

### `$ErrorActionPreference = 'Stop'` + bare `pip` = terminating error

With `Stop`, an unresolvable command name (e.g. bare `pip` when only the `py` launcher is installed) throws a terminating `CommandNotFoundException` that bypasses `try { } catch { }` if not specifically caught. Probe with `Get-Command -ErrorAction SilentlyContinue` before invoking, or wrap in `try`/`catch [System.Management.Automation.CommandNotFoundException]`.

## `install-release.sh` — install any release on a Mac (maintainers)

`tools/install-release.sh [alpha|beta|rc|stable|latest|<tag>]` picks the newest release of that kind (by creation date, drafts included), downloads its DMG with the `gh` login, and replaces `/Applications/MIDI Captain MAX Config Editor.app`. `list` shows recent releases; `--dry-run` downloads and mounts without installing. Alphas aren't on Homebrew (`homebrew.yml` skips them), so this is how to put one on a test machine. Drafts are only visible to repo members, which is why it needs `gh` rather than a public URL.

- **Newest = creation date, not version sort.** A mistyped tag (`v1.140.0-beta.1` exists) would win a version sort forever.
- **Homebrew copies:** overwriting a cask-installed app leaves Homebrew believing the old version, so the script offers to `brew uninstall` the cask first (`--yes` skips the prompt).
- **No clone needed:** `bash <(gh api repos/MC-Music-Workshop/midi-captain-max/contents/tools/install-release.sh -H "Accept: application/vnd.github.raw") alpha`. Don't make it read its own file (`$0`): under `bash <(...)` that's a one-shot pipe already consumed.
- **`set -o pipefail` + `| head`** exits 141 (SIGPIPE) once `head` closes the pipe; limit at the source (`gh ... --limit`) instead.
