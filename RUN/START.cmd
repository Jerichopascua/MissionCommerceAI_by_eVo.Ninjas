@echo off
REM Double-click me. Runs START.ps1 from this folder, whatever folder you are in.
powershell -ExecutionPolicy Bypass -File "%~dp0START.ps1" %*
echo.
pause
