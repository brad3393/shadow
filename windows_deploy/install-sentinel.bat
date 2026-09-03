@echo off
setlocal
set "DEST=%LOCALAPPDATA%\Shadow"
if not exist "%DEST%" mkdir "%DEST%"
copy /y "%~dp0watch-usb.ps1" "%DEST%\watch-usb.ps1" >nul
if errorlevel 1 ( echo Could not copy watcher. & pause & exit /b 1 )
schtasks /create /f /tn "ShadowSentinel" /tr "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File \"%DEST%\watch-usb.ps1\"" /sc onlogon >nul
if errorlevel 1 ( echo Could not register logon task. & pause & exit /b 1 )
schtasks /run /tn "ShadowSentinel" >nul
echo.
echo  Shadow Sentinel installed!
echo  From now on, plugging in the SHADOW-DEPLOY stick starts Shadow automatically.
echo  Undo later with uninstall-sentinel.bat
echo.
pause
endlocal
