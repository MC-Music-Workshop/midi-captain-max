#!/bin/bash
# Install any MIDI Captain MAX Config Editor release on this Mac, including alphas
# and unpublished drafts, without clicking through GitHub. Maintainer tool: uses
# your `gh` login (drafts are only visible to repo members).
#
# Usage:
#   tools/install-release.sh [alpha|beta|rc|stable|latest|<tag>] [--dry-run] [--yes]
#   tools/install-release.sh list            # recent releases, newest first
#
#   alpha|beta|rc|stable  newest release of that kind (by creation date, drafts included)
#   latest                newest release of any kind (default)
#   <tag>                 an exact tag, e.g. v1.15.0-beta.3
#   --dry-run             download and check the DMG, don't touch /Applications
#   --yes                 don't ask before replacing a Homebrew-installed copy
#
# No clone needed (e.g. on a music station):
#   bash <(gh api repos/MC-Music-Workshop/midi-captain-max/contents/tools/install-release.sh \
#     -H "Accept: application/vnd.github.raw") alpha
#
# The editor bundles that release's firmware, so installing it also gets you the
# matching firmware (install it on the pedal from the editor).

set -euo pipefail

REPO="MC-Music-Workshop/midi-captain-max"
APP_NAME="MIDI Captain MAX Config Editor"
APP_DEST="/Applications/${APP_NAME}.app"
CASKS=("midi-captain-max" "midi-captain-max@beta")

want="latest"
dry_run=false
assume_yes=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=true ;;
    --yes|-y) assume_yes=true ;;
    -h|--help)
      echo "Usage: install-release.sh [alpha|beta|rc|stable|latest|<tag>|list] [--dry-run] [--yes]"
      exit 0 ;;
    *) want="$arg" ;;
  esac
done

if [ "$(uname)" != "Darwin" ]; then
  echo "This installs the macOS app. On Windows/Linux, download from https://github.com/$REPO/releases" >&2
  exit 1
fi
command -v gh > /dev/null || { echo "Needs the GitHub CLI: brew install gh && gh auth login" >&2; exit 1; }

# Newest first by creation date (not version sort: a mistyped tag like
# v1.140.0-beta.1 would otherwise win forever). Drafts are included for repo members.
releases() {
  gh release list -R "$REPO" --limit "${1:-100}" --json tagName,isDraft,createdAt \
    --jq '.[] | "\(.tagName) \(if .isDraft then "draft" else "published" end) \(.createdAt[0:10])"'
}

# Tag format: v{major}.{minor}.{patch}[-{alpha|beta|rc}.{n}]
kind_of() {
  case "$1" in
    *-alpha*) echo alpha ;;
    *-beta*) echo beta ;;
    *-rc*) echo rc ;;
    *-*) echo other ;;
    *) echo stable ;;
  esac
}

if [ "$want" = "list" ]; then
  releases 20 | while read -r tag state date; do
    printf "%-22s %-7s %-10s %s\n" "$tag" "$(kind_of "$tag")" "$state" "$date"
  done
  exit 0
fi

case "$want" in
  alpha|beta|rc|stable|latest)
    tag=""
    while read -r t _ _; do
      if [ "$want" = "latest" ] || [ "$(kind_of "$t")" = "$want" ]; then
        tag="$t"
        break
      fi
    done < <(releases)
    [ -n "$tag" ] || { echo "No $want release found in the last 100." >&2; exit 1; }
    ;;
  v*) tag="$want" ;;
  *) echo "Unknown argument '$want'. Use alpha, beta, rc, stable, latest, list, or a tag like v1.15.0-beta.3." >&2; exit 1 ;;
esac

dmg="MIDI-Captain-MAX-Config-Editor-${tag}.dmg"
echo "Release: $tag ($(kind_of "$tag"))"

work="$(mktemp -d)"
mnt="$work/mnt"
# Always detach the image and remove temp files, even on failure.
cleanup() {
  hdiutil detach "$mnt" -quiet 2> /dev/null || true
  rm -rf "$work"
}
trap cleanup EXIT

if ! gh release download "$tag" -R "$REPO" -p "$dmg" -D "$work" 2> "$work/err"; then
  echo "Couldn't download $dmg from $tag:" >&2
  cat "$work/err" >&2
  echo "Assets on that release:" >&2
  gh release view "$tag" -R "$REPO" --json assets --jq '.assets[].name' >&2 || true
  exit 1
fi

mkdir -p "$mnt"
hdiutil attach "$work/$dmg" -nobrowse -readonly -mountpoint "$mnt" -quiet
src="$mnt/${APP_NAME}.app"
[ -d "$src" ] || { echo "No '${APP_NAME}.app' inside $dmg" >&2; exit 1; }
version="$(defaults read "$src/Contents/Info" CFBundleShortVersionString 2> /dev/null || echo "?")"

if $dry_run; then
  echo "Dry run: $dmg downloaded and mounted OK (app version $version). /Applications not touched."
  exit 0
fi

# A Homebrew-installed copy would lose track of its version if we overwrite it.
if command -v brew > /dev/null; then
  for cask in "${CASKS[@]}"; do
    if brew list --cask "$cask" > /dev/null 2>&1; then
      if ! $assume_yes; then
        read -r -p "'$cask' is installed with Homebrew. Uninstall it and use this script instead? [y/N] " ans
        [[ "$ans" =~ ^[Yy]$ ]] || { echo "Left as is."; exit 1; }
      fi
      brew uninstall --cask "$cask"
    fi
  done
fi

# Replacing a running app works but leaves the old process running; quit it first.
osascript -e "quit app \"${APP_NAME}\"" > /dev/null 2>&1 || true

rm -rf "$APP_DEST"
ditto "$src" "$APP_DEST"
echo "Installed $APP_DEST (version $version, from $tag)."
