# Starts everything: the database service, PesoWeb (API), the screens and the results dashboard. Safe to run again: anything already running is left alone.
$repo = Split-Path -Parent $PSScriptRoot

# the database service (LocalDB) is not always running after a restart of the PC
if (Get-Command sqllocaldb -ErrorAction SilentlyContinue) {
    $state = (sqllocaldb info MSSQLLocalDB 2>&1 | Select-String 'State:' | Out-String).Trim()
    if ($state -notmatch 'Running') {
        Write-Host 'Starting the database service (LocalDB)...'
        sqllocaldb start MSSQLLocalDB | Out-Null
    }
} else {
    Write-Warning 'The database service tool (sqllocaldb) was not found. Is SQL Server LocalDB installed?'
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Warning 'Python was not found. The system starts, but AGENT-REAL.cmd (the AI helper) will not work until Python is installed.'
}

& powershell -ExecutionPolicy Bypass -File (Join-Path $repo 'ui\demo\start-demo.ps1')

Write-Host ''
Write-Host 'Ready. Open http://127.0.0.1:4200 and sign in as superuser@520minimart.test (password: RUN\CREDENTIALS.txt, section A).' -ForegroundColor Green
Write-Host 'Next: SAVE-SNAPSHOT.cmd (a safety copy), then AGENT-REAL.cmd (so the Run now buttons work).'
