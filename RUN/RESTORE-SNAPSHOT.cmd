@echo off
REM Double-click me. Runs RESTORE-SNAPSHOT.ps1 from this folder, whatever folder you are in.
powershell -ExecutionPolicy Bypass -File "%~dp0RESTORE-SNAPSHOT.ps1" %*
echo.
pause
