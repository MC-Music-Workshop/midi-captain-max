#!/bin/bash
# Test MIDI Captain firmware in emulator
# This script runs automated tests and verifies expected output

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EMULATOR_DIR="$SCRIPT_DIR/rp2040js-circuitpython"
UF2_FILE="$SCRIPT_DIR/circuitpython-7.3.1.uf2"
FS_DIR="$SCRIPT_DIR/fs"
LOG_FILE="$SCRIPT_DIR/test.log"

# Check if emulator is set up
if [ ! -d "$EMULATOR_DIR" ]; then
    echo "❌ Emulator not set up. Run ./emulator/setup.sh first"
    exit 1
fi

echo "🧪 Testing MIDI Captain firmware in emulator..."
echo ""

# Prepare fresh filesystem
echo "📁 Preparing firmware..."
rm -rf "$FS_DIR"
mkdir -p "$FS_DIR"
cp -r "$SCRIPT_DIR/../firmware/dev/"* "$FS_DIR/"

# Run emulator with timeout and capture output
echo "🚀 Starting emulator..."
cd "$EMULATOR_DIR"

# Run for 30 seconds and capture output
timeout 30 npm start -- --image="$UF2_FILE" --fs="$FS_DIR" > "$LOG_FILE" 2>&1 || true

echo "✅ Emulator run complete"
echo ""

# Analyze output
echo "📊 Test Results:"
echo "----------------------------------------"

PASSED=0
FAILED=0

# Test 1: Firmware boots
if grep -q "MIDI CAPTAIN CUSTOM FIRMWARE" "$LOG_FILE"; then
    echo "✅ Test 1: Firmware boot"
    PASSED=$((PASSED + 1))
else
    echo "❌ Test 1: Firmware boot FAILED"
    FAILED=$((FAILED + 1))
fi

# Test 2: Config loads (look for device detection or config messages)
if grep -q -E "(STD10|Mini6|Config loaded|Device detected)" "$LOG_FILE"; then
    echo "✅ Test 2: Config/device detection"
    PASSED=$((PASSED + 1))
else
    echo "❌ Test 2: Config/device detection FAILED"
    FAILED=$((FAILED + 1))
fi

# Test 3: No Python errors
if grep -q -E "(Traceback|SyntaxError|ImportError|AttributeError)" "$LOG_FILE"; then
    echo "❌ Test 3: No Python errors FAILED"
    FAILED=$((FAILED + 1))
else
    echo "✅ Test 3: No Python errors"
    PASSED=$((PASSED + 1))
fi

# Test 4: No CircuitPython crashes
if grep -q -E "(PANIC|HARD FAULT|Stack overflow)" "$LOG_FILE"; then
    echo "❌ Test 4: No crashes FAILED"
    FAILED=$((FAILED + 1))
else
    echo "✅ Test 4: No crashes"
    PASSED=$((PASSED + 1))
fi

echo "----------------------------------------"
echo ""
echo "Results: $PASSED passed, $FAILED failed"
echo ""

if [ $FAILED -gt 0 ]; then
    echo "❌ Tests FAILED"
    echo ""
    echo "Log excerpt:"
    tail -50 "$LOG_FILE"
    echo ""
    echo "Full log: $LOG_FILE"
    exit 1
else
    echo "✅ All tests PASSED"
    echo ""
    echo "Log saved to: $LOG_FILE"
    exit 0
fi
