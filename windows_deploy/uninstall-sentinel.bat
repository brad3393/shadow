@echo off
schtasks /delete /f /tn "ShadowSentinel" >nul 2>nul
echo Shadow Sentinel removed. USB stick will no longer auto-launch Shadow.
pause
