<#
.SYNOPSIS
    Deploy firmware to MIDI Captain device (Windows)

.DESCRIPTION
    Works from both development repository and distributed firmware package.
    PowerShell equivalent of deploy.sh for Windows users.

.PARAMETER Device
    First-time setup for a device type (one1, duo2, nano4, mini6, std10).
    Writes the correct config template, installs CircuitPython libraries,
    and deploys firmware. The go-to for new devices.

.PARAMETER ResetConfig
    Overwrite config.json with the device-type template defaults.
    Does not reinstall libraries.

.PARAMETER Install
    Check/install CircuitPython libraries without touching config.

.PARAMETER LibsOnly
    Only install libraries (no firmware copy).

.PARAMETER Eject
    Eject device after deploy (forces clean reload).

.PARAMETER Fresh
    Deprecated alias for -ResetConfig.

.PARAMETER MountPoint
    Drive letter or path of the CIRCUITPY device (e.g. D:\)

.EXAMPLE
    .\deploy.ps1                          # Quick deploy (sync firmware only)
    .\deploy.ps1 -Device nano4           # First-time NANO4 setup (config + libs + firmware)
    .\deploy.ps1 -ResetConfig            # Reset config.json to template defaults
    .\deploy.ps1 -Install                 # Re-check/install libraries
    .\deploy.ps1 -LibsOnly               # Just install CircuitPython libs
    .\deploy.ps1 -Eject                   # Deploy + eject (clean disconnect)
    .\deploy.ps1 -MountPoint E:\          # Custom mount point
#>

[CmdletBinding()]
param(
    [ValidateSet("one1", "duo2", "nano4", "mini6", "std10")]
    [string]$Device,
    [switch]$ResetConfig,
    [switch]$Install,
    [switch]$LibsOnly,
    [switch]$Eject,
    [switch]$Fresh,
    [string]$MountPoint
)

$ErrorActionPreference = "Stop"

# Handle -Fresh as deprecated alias for -ResetConfig
if ($Fresh) {
    Write-Host "WARNING: -Fresh is deprecated, use -ResetConfig" -ForegroundColor Yellow
    $ResetConfig = $true
}

# -Device implies -Install (libraries) and config write
if ($Device) {
    $Install = $true
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Auto-detect context: development repo vs. distributed package
if (Test-Path (Join-Path $ProjectRoot "firmware\dev")) {
    $DevDir = Join-Path $ProjectRoot "firmware\dev"
    $Context = "dev"
} elseif (Test-Path (Join-Path $ScriptDir "code.py")) {
    $DevDir = $ScriptDir
    $Context = "dist"
} elseif (Test-Path (Join-Path $ScriptDir "firmware")) {
    $DevDir = Join-Path $ScriptDir "firmware"
    $Context = "dist"
} else {
    Write-Host "ERROR: Cannot locate firmware files" -ForegroundColor Red
    Write-Host "Expected firmware\dev\ (dev repo) or code.py (distributed package)"
    exit 1
}

# Required CircuitPython libraries
$RequiredLibs = @(
    "adafruit_midi"
    "adafruit_display_text"
    "adafruit_st7789"
    "neopixel"
    "adafruit_debouncer"
)

# If LibsOnly is set, also enable Install
if ($LibsOnly) { $Install = $true }

Write-Host "=== MIDI Captain Firmware Deploy ===" -ForegroundColor Blue
Write-Host ""

# Cache WMI volume query (reused for mount detection, device type, and eject)
$AllVolumes = Get-CimInstance -ClassName Win32_Volume -ErrorAction SilentlyContinue

# Build candidate label list: well-known defaults + usb_drive_name from local config files
$CandidateLabels = @("CIRCUITPY", "MIDICAPTAIN")
$cfgFiles = @(
    (Join-Path $DevDir "config.json"),
    (Join-Path $DevDir "config-one1.json"),
    (Join-Path $DevDir "config-duo2.json"),
    (Join-Path $DevDir "config-mini6.json"),
    (Join-Path $DevDir "config-nano4.json")
)
foreach ($cfgFile in $cfgFiles) {
    if (Test-Path $cfgFile) {
        try {
            $cfgJson = Get-Content $cfgFile -Raw | ConvertFrom-Json
            if ($cfgJson.usb_drive_name -and $CandidateLabels -notcontains $cfgJson.usb_drive_name) {
                $CandidateLabels += $cfgJson.usb_drive_name
            }
        } catch { }
    }
}

# Auto-detect mount point if not specified
if (-not $MountPoint) {
    $drives = $AllVolumes | Where-Object { $CandidateLabels -contains $_.Label }
    if ($drives) {
        $drive = $drives | Select-Object -First 1
        $MountPoint = $drive.DriveLetter
        if (-not $MountPoint) {
            # Some volumes report via Name instead
            $MountPoint = $drive.Name
        }
    }
}

# Normalize mount point to ensure trailing backslash for drive roots
if ($MountPoint -and $MountPoint -match "^[A-Z]:$") {
    $MountPoint = "$MountPoint\"
}

# Check if device is mounted
if (-not $MountPoint -or -not (Test-Path $MountPoint)) {
    Write-Host "ERROR: Device not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Tried labels: $($CandidateLabels -join ', ')"
    Write-Host ""
    Write-Host "Check that your device is plugged in, then:"
    Write-Host "  Get-Volume                             # see all mounted drives"
    Write-Host "  .\deploy.ps1 -MountPoint E:\           # specify a drive letter directly"
    exit 1
}

Write-Host "Device found at $MountPoint" -ForegroundColor Green

# Install libraries if requested
if ($Install) {
    Write-Host ""
    Write-Host "Installing CircuitPython libraries..." -ForegroundColor Yellow

    # Check for circup
    $circupCmd = Get-Command circup -ErrorAction SilentlyContinue
    if (-not $circupCmd) {
        Write-Host "  circup not found. Installing..."
        pip install circup --quiet 2>$null
        $circupCmd = Get-Command circup -ErrorAction SilentlyContinue
        if (-not $circupCmd) {
            Write-Host "ERROR: Failed to install circup" -ForegroundColor Red
            Write-Host "  Try: pip install circup"
            exit 1
        }
    }
    Write-Host "circup available" -ForegroundColor Green

    # Install each library
    # --path: target the device mount point
    # --allow-unsupported: we target CP 7.x which circup considers EOL.
    #
    # We deliberately do NOT pass `--py`. Mixing circup's `.py` source with
    # the bundle's `.mpy` puts both forms in /lib for the same module, which
    # is fragile: any disturbance to mtime / directory entry order can flip
    # which form CircuitPython loads, and the `.py` form often pulls in
    # newer-CP-only modules (e.g. `busdisplay`) that crash on CP 7.
    foreach ($lib in $RequiredLibs) {
        Write-Host "  Installing $lib... " -NoNewline
        $result = & circup --path $MountPoint --allow-unsupported install $lib 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "done" -ForegroundColor Green
        } else {
            Write-Host "(already installed)" -ForegroundColor Yellow
        }
    }
    Write-Host "Libraries installed" -ForegroundColor Green

    # Exit early if libs-only mode
    if ($LibsOnly) {
        Write-Host ""
        Write-Host "Library installation complete!" -ForegroundColor Green
        exit 0
    }
}

Write-Host ""
Write-Host "Source: $DevDir"
Write-Host "Target: $MountPoint"
if ($Context -eq "dev") {
    Write-Host "Mode: Development"
} else {
    Write-Host "Mode: Distribution package"
}

# Detect device type: -Device flag > existing config on device > fallback std10
$DeviceType = ""
$configPath = Join-Path $MountPoint "config.json"
if ($Device) {
    $DeviceType = $Device
    Write-Host "Device type set via -Device: $DeviceType"
} elseif (Test-Path $configPath) {
    try {
        $configContent = Get-Content $configPath -Raw | ConvertFrom-Json
        if ($configContent.device) {
            $DeviceType = $configContent.device
        }
    } catch {
        # Ignore parse errors
    }
}

# Fallback: cannot determine device type without a config; default to std10
if (-not $DeviceType) {
    $DeviceType = "std10"
    Write-Host "WARNING: No device type detected - defaulting to std10. Use -Device TYPE to override." -ForegroundColor Yellow
}

Write-Host "Device type: $DeviceType"
Write-Host ""

# Select appropriate config file
if ($DeviceType -eq "one1") {
    $ConfigFile = Join-Path $DevDir "config-one1.json"
} elseif ($DeviceType -eq "duo2") {
    $ConfigFile = Join-Path $DevDir "config-duo2.json"
} elseif ($DeviceType -eq "nano4") {
    $ConfigFile = Join-Path $DevDir "config-nano4.json"
} elseif ($DeviceType -eq "mini6") {
    $ConfigFile = Join-Path $DevDir "config-mini6.json"
} else {
    $ConfigFile = Join-Path $DevDir "config.json"
}

# Check if the device filesystem is writable
$writeTestFile = Join-Path $MountPoint ".deploy_write_test"
try {
    [System.IO.File]::WriteAllText($writeTestFile, "test")
    Remove-Item $writeTestFile -Force -ErrorAction SilentlyContinue
} catch {
    Write-Host "ERROR: Device filesystem is read-only" -ForegroundColor Red
    Write-Host ""
    Write-Host "The MIDI Captain drive is mounted but not writable." -ForegroundColor Yellow
    Write-Host ""
    $bootPyPath = Join-Path $MountPoint "boot.py"
    if (Test-Path $bootPyPath) {
        Write-Host "Our firmware is installed. To enable write access:" -ForegroundColor Yellow
        Write-Host "  1. Hold switch 1 (top-left footswitch) while plugging in USB"
        Write-Host "  2. The device will boot with USB write access enabled"
        Write-Host "  3. Run deploy.ps1 again"
    } else {
        Write-Host "This looks like a first-time install." -ForegroundColor Yellow
        Write-Host "The OEM firmware may have the USB drive in read-only mode."
        Write-Host ""
        Write-Host "Option A - CircuitPython safe mode (easiest):" -ForegroundColor Yellow
        Write-Host "  1. Briefly short the RUN pin to GND twice in quick succession"
        Write-Host "     (or rapidly plug/unplug USB twice if no RUN pin access)"
        Write-Host "     Status LED will flash yellow - safe mode is active"
        Write-Host "  2. Run deploy.ps1 again - the drive will be writable"
        Write-Host ""
        Write-Host "Option B - Hold the update button during power-on:" -ForegroundColor Yellow
        Write-Host "  1. Hold switch 1 (top-left footswitch) while plugging in USB"
        Write-Host "  2. Run deploy.ps1 again"
        Write-Host ""
        Write-Host "Option C - Reinstall CircuitPython:" -ForegroundColor Yellow
        Write-Host "  1. Hold Switch 1 (top-left footswitch) while plugging in USB -> RPI-RP2 drive appears"
        Write-Host "  2. Copy CircuitPython .uf2 to the RPI-RP2 drive"
        Write-Host "  3. Run deploy.ps1 again"
    }
    exit 1
}

# --- Helper function: sync a directory with --delete behavior ---
function Sync-Directory {
    param(
        [string]$Source,
        [string]$Destination,
        [switch]$Delete
    )

    if (-not (Test-Path $Source)) { return }
    if (-not (Test-Path $Destination)) {
        New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    }

    # Copy changed files from source
    $sourceFiles = Get-ChildItem -Path $Source -Recurse -File |
        Where-Object {
            $_.Name -ne '.DS_Store' -and
            $_.Name -notlike '*.pyc' -and
            $_.FullName -notmatch '__pycache__'
        }

    $changeCount = 0
    foreach ($file in $sourceFiles) {
        $relativePath = $file.FullName.Substring($Source.TrimEnd('\').Length + 1)
        $destFile = Join-Path $Destination $relativePath
        $destDir = Split-Path $destFile -Parent

        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }

        $needsCopy = $true
        if (Test-Path $destFile) {
            # Compare by content hash (equivalent to rsync --checksum)
            $srcHash = (Get-FileHash $file.FullName -Algorithm MD5).Hash
            $dstHash = (Get-FileHash $destFile -Algorithm MD5).Hash
            if ($srcHash -eq $dstHash) {
                $needsCopy = $false
            }
        }

        if ($needsCopy) {
            Copy-Item -Path $file.FullName -Destination $destFile -Force
            Write-Host "  > $relativePath"
            $changeCount++
        }
    }

    # Delete stale files from destination (rsync --delete equivalent)
    if ($Delete) {
        $destFiles = Get-ChildItem -Path $Destination -Recurse -File -ErrorAction SilentlyContinue
        foreach ($file in $destFiles) {
            $relativePath = $file.FullName.Substring($Destination.TrimEnd('\').Length + 1)
            $srcFile = Join-Path $Source $relativePath
            if (-not (Test-Path $srcFile)) {
                Remove-Item $file.FullName -Force
                Write-Host "  x $relativePath (removed)" -ForegroundColor Yellow
                $changeCount++
            }
        }
        # Clean up empty directories
        $destDirs = Get-ChildItem -Path $Destination -Recurse -Directory -ErrorAction SilentlyContinue |
                    Sort-Object { $_.FullName.Length } -Descending
        foreach ($dir in $destDirs) {
            if ((Get-ChildItem $dir.FullName -Force | Measure-Object).Count -eq 0) {
                Remove-Item $dir.FullName -Force
            }
        }
    }

    if ($changeCount -eq 0) {
        Write-Host "  (no changes)"
    }
}

# --- Helper function: sync a single file ---
function Sync-File {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path $Source)) { return }

    $needsCopy = $true
    if (Test-Path $Destination) {
        $srcHash = (Get-FileHash $Source -Algorithm MD5).Hash
        $dstHash = (Get-FileHash $Destination -Algorithm MD5).Hash
        if ($srcHash -eq $dstHash) {
            $needsCopy = $false
        }
    }

    if ($needsCopy) {
        $destDir = Split-Path $Destination -Parent
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        Copy-Item -Path $Source -Destination $Destination -Force
        Write-Host "  > $(Split-Path $Destination -Leaf)"
    } else {
        Write-Host "  (no changes)"
    }
}

Write-Host "Deploying changed files..."

# 1. boot.py first (keeps autoreload disabled)
Write-Host "boot.py:" -ForegroundColor Cyan
Sync-File -Source (Join-Path $DevDir "boot.py") -Destination (Join-Path $MountPoint "boot.py")

# 2. Core modules, device definitions, and fonts
Write-Host "core/:" -ForegroundColor Cyan
Sync-Directory -Source (Join-Path $DevDir "core") -Destination (Join-Path $MountPoint "core") -Delete

Write-Host "devices/:" -ForegroundColor Cyan
Sync-Directory -Source (Join-Path $DevDir "devices") -Destination (Join-Path $MountPoint "devices") -Delete

Write-Host "fonts/:" -ForegroundColor Cyan
Sync-Directory -Source (Join-Path $DevDir "fonts") -Destination (Join-Path $MountPoint "fonts")

Write-Host "lib/:" -ForegroundColor Cyan
Sync-Directory -Source (Join-Path $DevDir "lib") -Destination (Join-Path $MountPoint "lib")

# Drive letter for filesystem flush (used after all writes complete)
$driveLetter = $MountPoint.TrimEnd('\')

# 3. Deploy config
# -Device: always write config (first-time setup for this device type)
# -ResetConfig: overwrite existing config with template defaults
# No flag: only write config if one doesn't exist yet (preserve user customizations)
$WriteConfig = $false
if ($Device) {
    $WriteConfig = $true
    if (Test-Path $configPath) {
        Write-Host "Writing config.json for $DeviceType (-Device mode)..."
    } else {
        Write-Host "Installing config.json for $DeviceType..."
    }
} elseif ($ResetConfig) {
    $WriteConfig = $true
    Write-Host "Resetting config.json to $DeviceType template defaults (-ResetConfig)..."
} elseif (-not (Test-Path $configPath)) {
    $WriteConfig = $true
    Write-Host "Installing default config.json (device-specific)..."
} else {
    Write-Host "Preserving existing config.json (use -ResetConfig to overwrite)"
}

if ($WriteConfig) {
    if (Test-Path $ConfigFile) {
        Sync-File -Source $ConfigFile -Destination $configPath
    } else {
        Sync-File -Source (Join-Path $DevDir "config.json") -Destination $configPath
    }
}

# 4. Deploy device-specific fallback configs (reference only)
Write-Host "config-one1.json:" -ForegroundColor Cyan
Sync-File -Source (Join-Path $DevDir "config-one1.json") -Destination (Join-Path $MountPoint "config-one1.json")
Write-Host "config-duo2.json:" -ForegroundColor Cyan
Sync-File -Source (Join-Path $DevDir "config-duo2.json") -Destination (Join-Path $MountPoint "config-duo2.json")
Write-Host "config-mini6.json:" -ForegroundColor Cyan
Sync-File -Source (Join-Path $DevDir "config-mini6.json") -Destination (Join-Path $MountPoint "config-mini6.json")
Write-Host "config-nano4.json:" -ForegroundColor Cyan
Sync-File -Source (Join-Path $DevDir "config-nano4.json") -Destination (Join-Path $MountPoint "config-nano4.json")

# 5. code.py LAST (all dependencies are now in place)
Write-Host "code.py:" -ForegroundColor Cyan
Sync-File -Source (Join-Path $DevDir "code.py") -Destination (Join-Path $MountPoint "code.py")

# 6. Write VERSION.txt file
if ($Context -eq "dist" -and (Test-Path (Join-Path $DevDir "VERSION.txt"))) {
    $Version = (Get-Content (Join-Path $DevDir "VERSION.txt") -Raw).Trim()
    Sync-File -Source (Join-Path $DevDir "VERSION.txt") -Destination (Join-Path $MountPoint "VERSION.txt")
} else {
    try {
        $Version = (git describe --tags --always 2>$null)
        if (-not $Version) { $Version = "dev" }
    } catch {
        $Version = "dev"
    }
    $Version | Out-File -FilePath (Join-Path $MountPoint "VERSION.txt") -Encoding utf8 -NoNewline
    $Version | Out-File -FilePath (Join-Path $DevDir "VERSION.txt") -Encoding utf8 -NoNewline
}
Write-Host "Version: $Version"

# 7. Generate firmware manifest
Write-Host "Generating firmware manifest..."
$manifestLines = @()
Push-Location $DevDir
$files = Get-ChildItem -Recurse -File |
    Where-Object {
        $_.Name -notlike '*.pyc' -and
        $_.FullName -notmatch '__pycache__' -and
        $_.FullName -notmatch '[/\\]experiments[/\\]' -and
        $_.Name -ne 'firmware.md5' -and
        $_.Name -ne '.DS_Store'
    } |
    Sort-Object { $_.FullName }
foreach ($file in $files) {
    $relativePath = "./" + $file.FullName.Substring($DevDir.TrimEnd('\').Length + 1).Replace('\', '/')
    $hash = (Get-FileHash $file.FullName -Algorithm MD5).Hash.ToLower()
    $manifestLines += "$hash  $relativePath"
}
Pop-Location
$manifestLines -join "`n" | Out-File -FilePath (Join-Path $MountPoint "firmware.md5") -Encoding utf8 -NoNewline

# Final flush to ensure all writes reach the USB device
& cmd /c "fsutil volume flush $driveLetter" 2>$null | Out-Null

Write-Host ""

if ($Eject) {
    Write-Host "Ejecting device..."
    try {
        $vol = $AllVolumes | Where-Object { $_.DriveLetter -eq $driveLetter }
        if ($vol) {
            # Use Windows Shell to eject removable drive
            $shell = New-Object -ComObject Shell.Application
            $driveObj = $shell.Namespace(17).ParseName($driveLetter)
            if ($driveObj) {
                $driveObj.InvokeVerb("Eject")
                Write-Host "Deploy complete! Reconnect device to start firmware." -ForegroundColor Green
            } else {
                Write-Host "Deploy complete! Please safely eject the device manually." -ForegroundColor Green
            }
        }
    } catch {
        Write-Host "Deploy complete! Please safely eject the device manually." -ForegroundColor Green
    }
} else {
    Write-Host "Deploy complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "To reload the firmware:"
    Write-Host "  - Open serial console and press Ctrl+D"
    Write-Host "  - Or: Power-cycle the device"
    Write-Host "  - Or: Re-run with -Eject to force clean reload"
}
