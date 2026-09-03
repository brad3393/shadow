@echo off
setlocal enabledelayedexpansion
title Shadow
set "KIT_DIR=%~dp0"
if exist "%KIT_DIR%shadow\main.py" ( set "SHADOW_DIR=%KIT_DIR%shadow" ) else ( set "SHADOW_DIR=%KIT_DIR%" )
set "PY_CMD="
if exist "%KIT_DIR%python_embed\python.exe" set "PY_CMD=%KIT_DIR%python_embed\python.exe"
if not defined PY_CMD ( where python >nul 2>nul && set "PY_CMD=python" )
if not defined PY_CMD ( where py >nul 2>nul && set "PY_CMD=py -3" )
if not defined PY_CMD ( echo No Python found. Put python_embed\ on the stick or install from python.org & pause & exit /b 1 )
cd /d "%SHADOW_DIR%"
if not exist "main.py" ( echo main.py not found in %SHADOW_DIR% & pause & exit /b 1 )
echo ============================================================
echo    SHADOW  -  autonomous AI network
echo ============================================================
echo [1/3] Verifying Shadow install...
%PY_CMD% main.py --status
if errorlevel 1 ( echo Self-check failed. & pause & exit /b 1 )
echo OK - all systems verified.

REM --- secure bind: Tailscale only, never the raw LAN ----------
set "TS_IP="
set "TS_BIN=%ProgramFiles%\Tailscale\tailscale.exe"
if not exist "%TS_BIN%" set "TS_BIN=%ProgramFiles(x86)%\Tailscale\tailscale.exe"
if exist "%TS_BIN%" (
  for /f "usebackq delims=" %%i in (`"%TS_BIN%" ip -4 2^>nul`) do (
    if not defined TS_IP set "TS_IP=%%i"
  )
)
if defined TS_IP (
  set "BIND=!TS_IP!"
  echo [2/3] SECURE TUNNEL MODE: API binds to Tailscale interface !BIND!
  echo       Hotel/LAN neighbors cannot see or reach Shadow.
  echo       From your phone:  http://!BIND!:8787
) else (
  set "BIND=127.0.0.1"
  echo [2/3] Tailscale not detected - API binds to localhost only ^(safe standby^).
  echo       Shadow is unreachable from the network. For secure phone
  echo       access install Tailscale on both devices, then re-plug:
  echo       https://tailscale.com/download
)

set "SHADOW_PORT=8787"
netstat -ano | findstr ":%SHADOW_PORT% " | findstr "LISTENING" >nul
if errorlevel 1 (
  start "Shadow API" /min cmd /c "%PY_CMD% api_server.py --host %BIND% --port %SHADOW_PORT%"
  timeout /t 2 >nul
) else ( echo       API already running on port %SHADOW_PORT%. )
echo [3/3] Starting Shadow command line...
%PY_CMD% main.py
endlocal
