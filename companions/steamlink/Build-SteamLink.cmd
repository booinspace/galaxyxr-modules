@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "XR_WSL_ARGS="
if defined XR_WSL_DISTRO set XR_WSL_ARGS=--distribution "%XR_WSL_DISTRO%"
where wsl.exe >nul 2>nul
if errorlevel 1 (
  echo WSL is required. Install Ubuntu with Python 3, Java 21 and Android SDK Build Tools.
  if not defined XR_STEAMLINK_NO_PAUSE pause
  exit /b 1
)
wsl.exe %XR_WSL_ARGS% --exec python3 -u - --output "%~dp0output" %* < "%~dp0build_steamlink.py"
set "XR_EXIT=%ERRORLEVEL%"
if not "%XR_EXIT%"=="0" echo Build failed. Read the error above; no headset software was changed.
if not defined XR_STEAMLINK_NO_PAUSE pause
exit /b %XR_EXIT%
