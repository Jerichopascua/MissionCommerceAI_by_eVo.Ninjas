@echo off
REM Double-click me. Runs AGENT-REAL.ps1 from this folder, whatever folder you are in.
powershell -ExecutionPolicy Bypass -File "%~dp0AGENT-REAL.ps1" %*
echo.
pause
