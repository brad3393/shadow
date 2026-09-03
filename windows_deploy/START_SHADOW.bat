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
set "SHADOW_PORT=8787"
netstat -ano | findstr ":%SHADOW_PORT% " | findstr "LISTENING" >nul
if errorlevel 1 (
  echo [2/3] Starting REST API server on port %SHADOW_PORT%...
  start "Shadow API" /min cmd /c "%PY_CMD% api_server.py --host 0.0.0.0 --port %SHADOW_PORT%"
  timeout /t 2 >nul
) else ( echo [2/3] REST API already running on port %SHADOW_PORT%. )
echo OK - phone can reach Shadow at http://[laptop-ip]:%SHADOW_PORT%
echo (first run: Windows firewall prompt - tick Private networks + Allow)
echo [3/3] Starting Shadow command line...
%PY_CMD% main.py
endlocal
