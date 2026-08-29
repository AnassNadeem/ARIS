@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
if not exist "scripts\aris-home-tunnel.ps1" (
  echo Could not find the ARIS repo from this launcher.
  pause
  exit /b 1
)
if exist "%ProgramFiles%\nodejs\node.exe" set "PATH=%ProgramFiles%\nodejs;%PATH%"
if exist "%LocalAppData%\fnm" set "PATH=%LocalAppData%\fnm;%PATH%"
echo Starting ARIS home tunnel. Leave this window open.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0aris-home-tunnel.ps1"
echo.
echo The tunnel script exited. The public API is down until you run this again.
pause
