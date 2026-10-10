@echo off
rem Serves the customer app so you can open it on this PC and on a phone on the same Wi-Fi.
cd /d "%~dp0"
echo.
echo   On this PC:   http://localhost:8090
echo   On a phone (same Wi-Fi), use this PC's address, for example http://192.168.1.10:8090
echo   Find it with:  ipconfig   (IPv4 Address)
echo   Press Ctrl+C to stop.
echo.
python -m http.server 8090
