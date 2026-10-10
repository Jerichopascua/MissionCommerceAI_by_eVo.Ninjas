# Is everything ready? Reads only; changes nothing. Each line says OK or what to do.
. (Join-Path $PSScriptRoot '_structure.ps1')
$ok = $true
function Show($good, $what, $fix) {
    if ($good) { Write-Host ('  [ OK ] ' + $what) -ForegroundColor Green }
    else { Write-Host ('  [ !! ] ' + $what) -ForegroundColor Red; if ($fix) { Write-Host ('         -> ' + $fix) }; $script:ok = $false }
}
Write-Host 'Checking the test bench...'
Show ([bool](Get-Command python -ErrorAction SilentlyContinue)) 'Python is installed' 'Install Python 3 (python.org); AGENT-REAL.cmd needs it.'
Show ([bool](Get-Command sqlcmd -ErrorAction SilentlyContinue)) 'The database command tool (sqlcmd) is installed' 'Install the SQL Server command line utilities.'
$state = if (Get-Command sqllocaldb -ErrorAction SilentlyContinue) { (sqllocaldb info MSSQLLocalDB 2>&1 | Out-String) } else { '' }
Show ($state -match 'Running') 'The database service (LocalDB) is running' 'Double-click START.cmd; it starts it for you.'
$dbOk = $false
try { $n = sqlcmd -S '(localdb)\MSSQLLocalDB' -d PesoWeb_MissionDev -E -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(DISTINCT TenantID) FROM Users" 2>$null; $dbOk = ($LASTEXITCODE -eq 0 -and $n) } catch { }
Show $dbOk ("The database PesoWeb_MissionDev answers" + $(if ($dbOk) { " ($($n.Trim()) companies)" } else { '' })) 'Start the database service (START.cmd). If it still fails the database may be missing.'
foreach ($p in @(@(5071, 'PesoWeb (the API)'), @(4200, 'The screens'), @(8080, 'The results dashboard'))) {
    $up = [bool](Get-NetTCPConnection -LocalPort $p[0] -State Listen -ErrorAction SilentlyContinue)
    Show $up ("$($p[1]) is running on port $($p[0])") 'Double-click START.cmd and wait 2 minutes.'
}
$free = [math]::Round((Get-PSDrive D).Free / 1GB, 1)
Show ($free -ge 2) ("Drive D has $free GB free (needs 2 or more for safety copies)") 'Free some space on drive D.'
Show (Test-Path 'D:\PesoWeb_Backups') 'The safety-copy folder D:\PesoWeb_Backups exists' 'It is created the first time you run SAVE-SNAPSHOT.cmd.'

if ($dbOk) {
    $now = Get-DatabaseStructure
    $copies = Get-ChildItem 'D:\PesoWeb_Backups' -Filter '*.bak' -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    $usable = 0
    foreach ($c in $copies) {
        $note = $c.FullName -replace '\.bak$', '.structure.txt'
        if ((Test-Path $note) -and -not (Compare-Structure -Saved (Get-Content $note -Raw) -Now $now)) { $usable++ }
    }
    Write-Host ''
    Write-Host ("  Safety copies in D:\PesoWeb_Backups: {0}; restorable into the database as it is now: {1}" -f @($copies).Count, $usable)
    if ($usable -eq 0) { Write-Host '  -> None can be restored right now. Run SAVE-SNAPSHOT.cmd before you change anything.' }
}
Write-Host ''
if ($ok) { Write-Host 'Everything needed is in place.' -ForegroundColor Green } else { Write-Host 'Fix the lines marked !! and run this again.' -ForegroundColor Yellow }
