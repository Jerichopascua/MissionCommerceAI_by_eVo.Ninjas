@echo off
REM Double-click me. Runs STOP.ps1 from this folder, whatever folder you are in.
powershell -ExecutionPolicy Bypass -File "%~dp0STOP.ps1" %*
echo.
pause
