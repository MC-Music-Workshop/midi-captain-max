#!/bin/bash
# Deploy firmware to MIDI Captain device
#
# Works from both development repository and distributed firmware package.
#
# Usage: ./deploy.sh [options] [mount_point]
#
# Options:
#   --device TYPE   First-time setup for a device type (one1, duo2, nano4, mini6, std10).
#                   Writes the correct config template, installs CircuitPython
#                   libraries, and deploys firmware. The go-to for new devices.
#   --reset-config  Overwrite config.json with the device-type template defaults.
#                   Does not reinstall libraries.
#   --install       Check/install CircuitPython libraries without touching config.
#   --libs-only     Only install libraries (no firmware copy).
#   --eject         Eject device after deploy (forces clean reload).
#
# Examples:
#   ./deploy.sh                          # Quick deploy (sync firmware only)
#   ./deploy.sh --device nano4           # First-time NANO4 setup (config + libs + firmware)
#   ./deploy.sh --reset-config           # Reset config.json to template defaults
#   ./deploy.sh --install                # Re-check/install libraries
#   ./deploy.sh --eject                  # Deploy + eject (clean disconnect)
#   ./deploy.sh /Volumes/MIDICAPT        # Custom mount point
#
# Requires boot.py on device with autoreload disabled for best results.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Auto-detect context: development repo vs. distributed package
if [ -d "$PROJECT_ROOT/firmware/dev" ]; then
    # Running from development repository
    DEV_DIR="$PROJECT_ROOT/firmware/dev"
    CONTEXT="dev"
elif [ -f "$SCRIPT_DIR/code.py" ] || [ -d "$SCRIPT_DIR/firmware" ]; then
    # Running from distributed package (firmware files in same dir or firmware/ subdir)
    if [ -f "$SCRIPT_DIR/code.py" ]; then
        DEV_DIR="$SCRIPT_DIR"
    else
        DEV_DIR="$SCRIPT_DIR/firmware"
    fi
    CONTEXT="dist"
else
    echo -e "${RED}❌ Cannot locate firmware files${NC}"
    echo "Expected firmware/dev/ (dev repo) or code.py (distributed package)"
    exit 1
fi

MOUNT_POINT="/Volumes/CIRCUITPY"
DO_EJECT=false
DO_RESET=false
DO_INSTALL=false
LIBS_ONLY=false
DO_RESET_CONFIG=false
FORCE_DEVICE_TYPE=""

# Required CircuitPython libraries
REQUIRED_LIBS=(
    "adafruit_midi"
    "adafruit_display_text"
    "adafruit_st7789"
    "neopixel"
    "adafruit_debouncer"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Valid device types
VALID_DEVICES="one1 duo2 nano4 mini6 std10"

# Parse arguments
ARGS=("$@")
i=0
while [ $i -lt ${#ARGS[@]} ]; do
    arg="${ARGS[$i]}"
    case $arg in
        --device)
            i=$((i + 1))
            if [ $i -ge ${#ARGS[@]} ]; then
                echo -e "${RED}❌ --device requires a type: $VALID_DEVICES${NC}"
                exit 1
            fi
            FORCE_DEVICE_TYPE="${ARGS[$i]}"
            # Validate device type
            if ! echo "$VALID_DEVICES" | grep -qw "$FORCE_DEVICE_TYPE"; then
                echo -e "${RED}❌ Unknown device type: $FORCE_DEVICE_TYPE${NC}"
                echo "Valid types: $VALID_DEVICES"
                exit 1
            fi
            ;;
        --install)
            DO_INSTALL=true
            ;;
        --libs-only)
            LIBS_ONLY=true
            DO_INSTALL=true
            ;;
        --eject)
            DO_EJECT=true
            ;;
        --reset-config)
            DO_RESET_CONFIG=true
            ;;
        --fresh)
            # Backwards compat: --fresh is now --reset-config
            echo -e "${YELLOW}⚠️  --fresh is deprecated, use --reset-config${NC}"
            DO_RESET_CONFIG=true
            ;;
        --help|-h)
            echo "Usage: ./deploy.sh [options] [mount_point]"
            echo ""
            echo "Options:"
            echo "  --device TYPE   First-time setup (config + libs + firmware)"
            echo "                  Valid types: $VALID_DEVICES"
            echo "  --reset-config  Overwrite config.json with template defaults"
            echo "  --install       Check/install CircuitPython libraries"
            echo "  --libs-only     Only install libraries (no firmware copy)"
            echo "  --eject         Eject device after deploy (forces clean reload)"
            echo ""
            echo "Quick deploy (no flags) syncs firmware only, preserves config."
            exit 0
            ;;
        /*)
            MOUNT_POINT="$arg"
            ;;
        *)
            echo -e "${RED}❌ Unknown argument: $arg${NC}"
            echo "Run ./deploy.sh --help for usage"
            exit 1
            ;;
    esac
    i=$((i + 1))
done

# --device implies --install (libraries) and config write
if [ -n "$FORCE_DEVICE_TYPE" ]; then
    DO_INSTALL=true
fi

echo -e "${BLUE}=== MIDI Captain Firmware Deploy ===${NC}"
echo ""

# Auto-detect mount point if not specified
if [ ! -d "$MOUNT_POINT" ]; then
    # Build candidate list: well-known defaults + usb_drive_name from local config files
    CANDIDATE_NAMES=("CIRCUITPY" "MIDICAPTAIN")
    for cfg_file in "$DEV_DIR/config.json" "$DEV_DIR/config-one1.json" "$DEV_DIR/config-duo2.json" "$DEV_DIR/config-mini6.json" "$DEV_DIR/config-nano4.json"; do
        if [ -f "$cfg_file" ]; then
            # Parse usb_drive_name: use jq if available, fall back to grep/sed
            if command -v jq &>/dev/null; then
                CNAME=$(jq -r '.usb_drive_name // empty' "$cfg_file" 2>/dev/null)
            else
                CNAME=$(grep -o '"usb_drive_name"[[:space:]]*:[[:space:]]*"[^"]*"' "$cfg_file" 2>/dev/null \
                        | sed 's/.*"\([^"]*\)"$/\1/')
            fi
            if [ -n "$CNAME" ]; then
                # Add only if not already in the list
                if ! printf '%s\n' "${CANDIDATE_NAMES[@]}" | grep -qx "$CNAME"; then
                    CANDIDATE_NAMES+=("$CNAME")
                fi
            fi
        fi
    done

    # Collect volume root directories for this platform
    VOLUME_ROOTS=()
    [ -d "/Volumes" ] && VOLUME_ROOTS+=("/Volumes")
    if [ -n "${USER:-}" ]; then
        [ -d "/media/$USER" ]     && VOLUME_ROOTS+=("/media/$USER")
        [ -d "/run/media/$USER" ] && VOLUME_ROOTS+=("/run/media/$USER")
    fi

    # Try each candidate under each volume root
    for vol_root in "${VOLUME_ROOTS[@]}"; do
        for cname in "${CANDIDATE_NAMES[@]}"; do
            if [ -d "$vol_root/$cname" ]; then
                MOUNT_POINT="$vol_root/$cname"
                break 2
            fi
        done
    done
fi

# Check if device is mounted
if [ ! -d "$MOUNT_POINT" ]; then
    echo -e "${RED}❌ Device not found${NC}"
    echo ""
    # Build a readable list of paths that were tried
    TRIED_PATHS=()
    for vol_root in "${VOLUME_ROOTS[@]}"; do
        for cname in "${CANDIDATE_NAMES[@]}"; do
            TRIED_PATHS+=("$vol_root/$cname")
        done
    done
    echo "Tried: ${TRIED_PATHS[*]}"
    echo ""
    echo "Check that your device is plugged in, then:"
    echo "  ls /Volumes/                        # see all mounted drives"
    echo "  ./deploy.sh /Volumes/MyDriveName    # specify a custom drive name"
    exit 1
fi

echo -e "${GREEN}✓ Device found at $MOUNT_POINT${NC}"

# Show current and incoming firmware versions
if [ -f "$MOUNT_POINT/VERSION.txt" ]; then
    CURRENT_VERSION=$(cat "$MOUNT_POINT/VERSION.txt")
    echo "  Current firmware: $CURRENT_VERSION"
else
    echo "  Current firmware: (none)"
fi
if [ "$CONTEXT" = "dist" ] && [ -f "$DEV_DIR/VERSION.txt" ]; then
    NEW_VERSION=$(cat "$DEV_DIR/VERSION.txt")
else
    NEW_VERSION=$(git describe --tags --always 2>/dev/null || echo "dev")
fi
echo "  Upgrading to:     $NEW_VERSION"

# Install libraries if requested (--install or --device)
if [ "$DO_INSTALL" = true ]; then
    echo ""
    echo -e "${YELLOW}📦 Installing CircuitPython libraries...${NC}"

    # Check for circup
    if ! command -v circup &> /dev/null; then
        echo "  circup not found. Installing..."
        pip install circup --quiet
        if ! command -v circup &> /dev/null; then
            echo -e "${RED}✗ Failed to install circup${NC}"
            echo "  Try: pip install circup"
            exit 1
        fi
    fi
    echo -e "${GREEN}✓ circup available${NC}"

    # Install each library (--path must come before the subcommand)
    # --allow-unsupported: we target CP 7.x which circup considers EOL.
    #
    # We deliberately do NOT pass `--py`. Mixing circup's `.py` source with
    # the bundle's `.mpy` puts both forms in /lib for the same module, which
    # is fragile: any disturbance to mtime / directory entry order can flip
    # which form CircuitPython loads, and the `.py` form often pulls in
    # newer-CP-only modules (e.g. `busdisplay`) that crash on CP 7.
    CIRCUP="circup --path $MOUNT_POINT --allow-unsupported"
    for lib in "${REQUIRED_LIBS[@]}"; do
        echo -n "  Installing $lib... "
        if $CIRCUP install "$lib" 2>/dev/null; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${YELLOW}(already installed)${NC}"
        fi
    done
    echo -e "${GREEN}✓ Libraries installed${NC}"

    # Exit early if libs-only mode
    if [ "$LIBS_ONLY" = true ]; then
        echo ""
        echo -e "${GREEN}✅ Library installation complete!${NC}"
        exit 0
    fi
fi

echo ""
echo "📁 Source: $DEV_DIR"
echo "📱 Target: $MOUNT_POINT"
if [ "$CONTEXT" = "dev" ]; then
    echo "🔧 Mode: Development"
else
    echo "📦 Mode: Distribution package"
fi

# Detect device type: --device flag > existing config on device > default std10
DEVICE_TYPE=""
if [ -n "$FORCE_DEVICE_TYPE" ]; then
    DEVICE_TYPE="$FORCE_DEVICE_TYPE"
    echo "📌 Device type set via --device: $DEVICE_TYPE"
elif [ -f "$MOUNT_POINT/config.json" ]; then
    # Try to read device type from existing config
    DETECTED=$(grep -o '"device"[[:space:]]*:[[:space:]]*"[^"]*"' "$MOUNT_POINT/config.json" 2>/dev/null | sed 's/.*"\([^"]*\)"$/\1/')
    if [ -n "$DETECTED" ]; then
        DEVICE_TYPE="$DETECTED"
    fi
fi

# Fallback: cannot determine device type without a config; default to std10
if [ -z "$DEVICE_TYPE" ]; then
    DEVICE_TYPE="std10"
    echo -e "${YELLOW}⚠️  No device type detected — defaulting to std10. Use --device TYPE to override.${NC}"
fi

echo "🎛️  Device type: $DEVICE_TYPE"
echo ""

# Select appropriate config file
if [ "$DEVICE_TYPE" = "one1" ]; then
    CONFIG_FILE="$DEV_DIR/config-one1.json"
elif [ "$DEVICE_TYPE" = "duo2" ]; then
    CONFIG_FILE="$DEV_DIR/config-duo2.json"
elif [ "$DEVICE_TYPE" = "nano4" ]; then
    CONFIG_FILE="$DEV_DIR/config-nano4.json"
elif [ "$DEVICE_TYPE" = "mini6" ]; then
    CONFIG_FILE="$DEV_DIR/config-mini6.json"
else
    CONFIG_FILE="$DEV_DIR/config.json"
fi

# Check if the device filesystem is writable before attempting deploy
if ! touch "$MOUNT_POINT/.deploy_write_test" 2>/dev/null; then
    echo -e "${RED}❌ Device filesystem is read-only${NC}"
    echo ""
    echo -e "${YELLOW}The MIDI Captain drive is mounted but not writable.${NC}"
    echo ""
    if [ -f "$MOUNT_POINT/boot.py" ]; then
        # boot.py exists: firmware already installed, device is in performance mode
        echo -e "${YELLOW}Our firmware is installed. To enable write access:${NC}"
        echo "  1. Hold switch 1 (top-left footswitch) while plugging in USB"
        echo "  2. The device will boot with USB write access enabled"
        echo "  3. Run deploy.sh again"
    else
        # No boot.py: likely first-time install over OEM firmware
        echo -e "${YELLOW}This looks like a first-time install.${NC}"
        echo "The OEM firmware may have the USB drive in read-only mode."
        echo ""
        echo -e "${YELLOW}Option A — CircuitPython safe mode (easiest):${NC}"
        echo "  1. Briefly short the RUN pin to GND twice in quick succession"
        echo "     (or rapidly plug/unplug USB twice if no RUN pin access)"
        echo "     Status LED will flash yellow — safe mode is active"
        echo "  2. Run deploy.sh again — the drive will be writable"
        echo ""
        echo -e "${YELLOW}Option B — Hold the update button during power-on:${NC}"
        echo "  1. Hold switch 1 (top-left footswitch) while plugging in USB"
        echo "  2. Run deploy.sh again"
        echo ""
        echo -e "${YELLOW}Option C — Reinstall CircuitPython:${NC}"
        echo "  1. Hold Switch 1 (top-left footswitch) while plugging in USB → RPI-RP2 drive appears"
        echo "  2. Copy CircuitPython .uf2 to the RPI-RP2 drive"
        echo "  3. Run deploy.sh again"
    fi
    exit 1
fi
rm -f "$MOUNT_POINT/.deploy_write_test" 2>/dev/null

echo "🚀 Deploying changed files..."

# Deploy dependencies first, code.py last. This ensures all imports are
# in place before the main entry point lands on the device.
#
# NOTE: This script deploys raw .py source files for rapid development.
# CI builds compile core/ and devices/ to .mpy bytecode for smaller/faster
# production firmware. See .github/workflows/ci.yml for the compile step.
#
# rsync flags:
# --checksum: compare by content, not just timestamp (more reliable for USB drives)
# --inplace: minimize file rewrites
# --itemize-changes: show what changed

# Sync a directory and show clean progress (label + changed files or "(no changes)")
# Usage: sync_dir LABEL SOURCE DEST [--delete]
sync_dir() {
    local label="$1" src="$2" dst="$3" delete_flag=""
    [ "${4:-}" = "--delete" ] && delete_flag="--delete"
    echo -e "${BLUE}${label}:${NC}"
    local output
    # rsync --itemize-changes format: "XYZtpog... filename"
    # Extract just the filename (field after the status flags)
    output=$(rsync -a --checksum --inplace --itemize-changes $delete_flag \
        --exclude='.DS_Store' --exclude='*.pyc' --exclude='__pycache__' \
        "$src" "$dst" 2>&1 \
        | sed 's/^[^ ]* //')
    if [ -z "$output" ]; then
        echo "  (no changes)"
    else
        echo "$output" | while IFS= read -r line; do
            [ -n "$line" ] && echo "  > $line"
        done
    fi
}

# Sync a single file and show clean progress
# Usage: sync_file LABEL SOURCE DEST
sync_file() {
    local label="$1" src="$2" dst="$3"
    echo -e "${BLUE}${label}:${NC}"
    local output
    output=$(rsync -a --checksum --inplace --itemize-changes "$src" "$dst" 2>&1)
    if [ -z "$output" ]; then
        echo "  (no changes)"
    else
        echo "  > $(basename "$src")"
    fi
}

# 1. boot.py first (keeps autoreload disabled)
sync_file "boot.py" "$DEV_DIR/boot.py" "$MOUNT_POINT/"

# 2. Core modules, device definitions, and fonts
# --delete removes stale files from the device (e.g. old .py source when
# deploying compiled .mpy from a package, or old .mpy when deploying .py
# source from the dev repo). Without --delete, both forms can coexist on
# the device and CircuitPython may load the wrong one, causing ImportErrors.
sync_dir "core/" "$DEV_DIR/core/" "$MOUNT_POINT/core/" --delete
sync_dir "devices/" "$DEV_DIR/devices/" "$MOUNT_POINT/devices/" --delete
sync_dir "fonts/" "$DEV_DIR/fonts/" "$MOUNT_POINT/fonts/"
sync_dir "lib/" "$DEV_DIR/lib/" "$MOUNT_POINT/lib/"

sync

# 3. Deploy config
# --device: always write config (first-time setup for this device type)
# --reset-config: overwrite existing config with template defaults
# No flag: only write config if one doesn't exist yet (preserve user customizations)
WRITE_CONFIG=false
if [ -n "$FORCE_DEVICE_TYPE" ]; then
    WRITE_CONFIG=true
    if [ -f "$MOUNT_POINT/config.json" ]; then
        echo "📝 Writing config.json for $DEVICE_TYPE (--device mode)..."
    else
        echo "📝 Installing config.json for $DEVICE_TYPE..."
    fi
elif [ "$DO_RESET_CONFIG" = true ]; then
    WRITE_CONFIG=true
    echo "📝 Resetting config.json to $DEVICE_TYPE template defaults (--reset-config)..."
elif [ ! -f "$MOUNT_POINT/config.json" ]; then
    WRITE_CONFIG=true
    echo "📝 Installing default config.json (device-specific)..."
else
    echo "📝 Preserving existing config.json (use --reset-config to overwrite)"
fi

if [ "$WRITE_CONFIG" = true ]; then
    if [ -f "$CONFIG_FILE" ]; then
        sync_file "config.json" "$CONFIG_FILE" "$MOUNT_POINT/config.json"
    else
        sync_file "config.json" "$DEV_DIR/config.json" "$MOUNT_POINT/config.json"
    fi
fi

# 4. Deploy device-specific fallback configs (reference only)
sync_file "config-one1.json" "$DEV_DIR/config-one1.json" "$MOUNT_POINT/config-one1.json"
sync_file "config-duo2.json" "$DEV_DIR/config-duo2.json" "$MOUNT_POINT/config-duo2.json"
sync_file "config-mini6.json" "$DEV_DIR/config-mini6.json" "$MOUNT_POINT/config-mini6.json"
sync_file "config-nano4.json" "$DEV_DIR/config-nano4.json" "$MOUNT_POINT/config-nano4.json"

# 5. code.py LAST (all dependencies are now in place)
sync_file "code.py" "$DEV_DIR/code.py" "$MOUNT_POINT/"

# 6. Write VERSION.txt file for firmware version display
# Distributed packages include a pre-built VERSION.txt file written by CI.
# Use it directly rather than falling back to "dev" via git describe.
if [ "$CONTEXT" = "dist" ] && [ -f "$DEV_DIR/VERSION.txt" ]; then
    VERSION=$(cat "$DEV_DIR/VERSION.txt")
    sync_file "VERSION.txt" "$DEV_DIR/VERSION.txt" "$MOUNT_POINT/VERSION.txt"
else
    VERSION=$(git describe --tags --always 2>/dev/null || echo "dev")
    echo "$VERSION" > "$MOUNT_POINT/VERSION.txt"
    echo "$VERSION" > "$DEV_DIR/VERSION.txt"
fi
echo "📌 Version: $VERSION"

# Sync filesystem
sync

# Generate manifest on device for incremental installer updates.
# The installer compares this against the firmware zip's manifest
# to skip unchanged files on subsequent installs.
echo "📋 Generating firmware manifest..."
# Detect checksum command: md5sum (Linux) or md5 -r (macOS)
if command -v md5sum &>/dev/null; then
    MD5_CMD="md5sum"
elif command -v md5 &>/dev/null; then
    MD5_CMD="md5 -r"
else
    MD5_CMD=""
fi
if [ -n "$MD5_CMD" ]; then
    (
      cd "$DEV_DIR"
      find . -type f \
        -not -name "*.pyc" \
        -not -path "*/__pycache__/*" \
        -not -path "*/experiments/*" \
        -not -name "firmware.md5" \
        -not -name ".DS_Store" \
        | sort \
        | xargs $MD5_CMD > "$MOUNT_POINT/firmware.md5"
    )
else
    echo "⚠️  Skipping firmware manifest (neither md5sum nor md5 found)"
fi

echo ""

if [ "$DO_EJECT" = true ]; then
    echo "⏏️  Ejecting device..."
    diskutil eject "$MOUNT_POINT" 2>/dev/null || true
    echo "✅ Deploy complete! Reconnect device to start firmware."
else
    echo "✅ Deploy complete!"
    echo ""
    echo "To reload the firmware:"
    echo "  • Open serial console and press Ctrl+D"
    echo "  • Or: Power-cycle the device"
    echo "  • Or: Re-run with --eject to force clean reload"
fi
