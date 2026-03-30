# Emulator Test Configurations

This directory contains test configuration files for emulator testing.

## Available Configs

- `test-std10.json` - STD10 10-switch device configuration
- `test-mini6.json` - Mini6 6-switch device configuration
- `test-toggle.json` - Test toggle mode buttons
- `test-momentary.json` - Test momentary mode buttons
- `test-mixed-modes.json` - Test mixed button modes

## Usage

```bash
# Run emulator with a specific config
./emulator/run.sh emulator/configs/test-std10.json

# Run automated tests with a specific config
cp emulator/configs/test-std10.json emulator/fs/config.json
./emulator/test.sh
```

## Creating Custom Configs

Copy one of the templates and modify:

```bash
cp emulator/configs/test-std10.json emulator/configs/my-test.json
# Edit my-test.json
./emulator/run.sh emulator/configs/my-test.json
```
