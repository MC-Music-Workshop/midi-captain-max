#!/bin/bash
# Setup script for MIDI Captain emulator testing
# This script downloads and configures rp2040js-circuitpython for testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EMULATOR_DIR="$SCRIPT_DIR/rp2040js-circuitpython"
UF2_URL="https://downloads.circuitpython.org/bin/raspberry_pi_pico/en_US/adafruit-circuitpython-raspberry_pi_pico-en_US-7.3.1.uf2"
UF2_FILE="$SCRIPT_DIR/circuitpython-7.3.1.uf2"

echo "=== MIDI Captain Emulator Setup ==="
echo ""

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js version 18+ required (found: $(node --version))"
    exit 1
fi

echo "✅ Node.js $(node --version) found"
echo ""

# Clone emulator if not exists
if [ ! -d "$EMULATOR_DIR" ]; then
    echo "📦 Cloning rp2040js-circuitpython..."
    git clone https://github.com/wokwi/rp2040js-circuitpython.git "$EMULATOR_DIR"
    echo "✅ Cloned successfully"
else
    echo "✅ Emulator already cloned"
fi

# Install dependencies
echo ""
echo "📦 Installing emulator dependencies..."
cd "$EMULATOR_DIR"
npm install
echo "✅ Dependencies installed"

# Download CircuitPython UF2
if [ ! -f "$UF2_FILE" ]; then
    echo ""
    echo "📥 Downloading CircuitPython 7.3.1 UF2..."
    curl -L -o "$UF2_FILE" "$UF2_URL"
    echo "✅ Downloaded successfully"
else
    echo ""
    echo "✅ CircuitPython UF2 already downloaded"
fi

# Prepare firmware filesystem
echo ""
echo "📁 Preparing firmware filesystem..."
FS_DIR="$SCRIPT_DIR/fs"
rm -rf "$FS_DIR"
mkdir -p "$FS_DIR"

# Copy firmware files
cp -r "$PROJECT_ROOT/firmware/dev/"* "$FS_DIR/"

# Ensure config.json exists
if [ ! -f "$FS_DIR/config.json" ]; then
    echo "⚠️  Warning: config.json not found, copying default"
    cp "$PROJECT_ROOT/firmware/dev/config.json" "$FS_DIR/config.json"
fi

echo "✅ Firmware filesystem ready at $FS_DIR"

# Summary
echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Emulator directory: $EMULATOR_DIR"
echo "CircuitPython UF2:  $UF2_FILE"
echo "Firmware files:     $FS_DIR"
echo ""
echo "Next steps:"
echo "  1. Run tests:     ./emulator/test.sh"
echo "  2. Run manually:  ./emulator/run.sh"
echo "  3. See docs:      docs/emulator-setup.md"
echo ""
