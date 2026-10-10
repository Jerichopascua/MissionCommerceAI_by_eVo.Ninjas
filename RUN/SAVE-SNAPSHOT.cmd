@echo off
REM Double-click me. Runs SAVE-SNAPSHOT.ps1 from this folder, whatever folder you are in.
powershell -ExecutionPolicy Bypass -File "%~dp0SAVE-SNAPSHOT.ps1" %*
echo.
pause
