@echo off
REM Launcher for deploy.ps1 on Windows.
REM .bat files are not subject to PowerShell's ExecutionPolicy, so this lets
REM users run the deploy even when unsigned .ps1 scripts are blocked.
REM -ExecutionPolicy Bypass applies to this one process only; it changes no
REM system policy. %~dp0 is this script's own directory (with trailing \),
REM so deploy.ps1 is found regardless of the current directory. %* forwards
REM all arguments (-Device, -MountPoint, etc.) through to the script.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy.ps1" %*
exit /b %ERRORLEVEL%
