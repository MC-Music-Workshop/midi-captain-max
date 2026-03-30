#!/bin/bash
# Run MIDI Captain firmware in emulator
# Usage: ./emulator/run.sh [config-file]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EMULATOR_DIR="$SCRIPT_DIR/rp2040js-circuitpython"
UF2_FILE="$SCRIPT_DIR/circuitpython-7.3.1.uf2"
FS_DIR="$SCRIPT_DIR/fs"
CONFIG_FILE="${1:-}"

# Check if emulator is set up
if [ ! -d "$EMULATOR_DIR" ]; then
    echo "❌ Emulator not set up. Run ./emulator/setup.sh first"
    exit 1
fi

if [ ! -f "$UF2_FILE" ]; then
    echo "❌ CircuitPython UF2 not found. Run ./emulator/setup.sh first"
    exit 1
fi

# Use custom config if provided
if [ -n "$CONFIG_FILE" ]; then
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "❌ Config file not found: $CONFIG_FILE"
        exit 1
    fi
    echo "📝 Using config: $CONFIG_FILE"
    cp "$CONFIG_FILE" "$FS_DIR/config.json"
fi

echo "🚀 Starting MIDI Captain emulator..."
echo ""
echo "Emulator:  rp2040js-circuitpython"
echo "Firmware:  CircuitPython 7.3.1"
echo "Code:      $FS_DIR/code.py"
echo "Config:    $FS_DIR/config.json"
echo ""
echo "Press Ctrl+C to exit"
echo ""
echo "----------------------------------------"
echo ""

cd "$EMULATOR_DIR"
npm start -- --image="$UF2_FILE" --fs="$FS_DIR"
