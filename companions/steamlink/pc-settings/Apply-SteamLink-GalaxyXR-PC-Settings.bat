@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

where powershell.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: Windows PowerShell was not found.
    pause
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Apply-SteamLink-GalaxyXR-PC-Settings.ps1"
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
    echo.
    echo The SteamVR settings tool did not complete.
    pause
)
exit /b %EXITCODE%
