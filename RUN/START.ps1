# Starts PesoWeb (API), the screens and the results dashboard. Safe to run again: anything already running is left alone.
$repo = Split-Path -Parent $PSScriptRoot
& powershell -ExecutionPolicy Bypass -File (Join-Path $repo 'ui\demo\start-demo.ps1')
