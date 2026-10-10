@echo off
REM Double-click me. Runs CHECK.ps1 from this folder, whatever folder you are in.
powershell -ExecutionPolicy Bypass -File "%~dp0CHECK.ps1" %*
echo.
pause
