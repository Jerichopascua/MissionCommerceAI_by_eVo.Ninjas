# Puts the whole database back to a safety copy made with SAVE-SNAPSHOT. Everything saved since that copy is replaced.
# It first saves a copy of the database as it is now (named before-restore-...), so even a restore can be undone.
#   RUN\RESTORE-SNAPSHOT.cmd                   (shows the copies and asks)
param(
    [string]$Name,
    [string]$Database = 'PesoWeb_MissionDev',
    [string]$Folder = 'D:\PesoWeb_Backups'
)
$ErrorActionPreference = 'Stop'
$copies = Get-ChildItem $Folder -Filter '*.bak' -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "$Database*" -or $_.Name -notlike 'PesoWeb_V2*' } | Sort-Object LastWriteTime -Descending
if (-not $Name) {
    if (-not $copies) { throw "No copies found in $Folder." }
    Write-Host "Safety copies in $Folder (newest first):"
    $copies | Select-Object -First 15 | ForEach-Object { Write-Host ('  {0}   {1}   {2} MB' -f $_.BaseName, $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm'), [math]::Round($_.Length / 1MB)) }
    $Name = Read-Host 'Which one? (type the name exactly, without .bak)'
}
$Name = $Name -replace '\.bak$', ''
$file = Join-Path $Folder ($Name + '.bak')
if (-not (Test-Path $file)) { throw "No such copy: $file" }
Write-Host "This replaces the WHOLE database ($Database) with '$Name' (every company, not only 520 Minimart)." -ForegroundColor Yellow
$confirm = Read-Host 'Type RESTORE to continue'
if ($confirm -cne 'RESTORE') { Write-Host 'Cancelled. Nothing was changed.'; exit 0 }

$undo = 'before-restore-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& (Join-Path $PSScriptRoot 'SAVE-SNAPSHOT.ps1') -Name $undo -Database $Database -Folder $Folder

foreach ($port in 5071) {                       # PesoWeb must not be using the database while it is replaced
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 3
$q = "ALTER DATABASE [$Database] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; RESTORE DATABASE [$Database] FROM DISK = N'$file' WITH REPLACE, CHECKSUM, RECOVERY; ALTER DATABASE [$Database] SET MULTI_USER;"
sqlcmd -S '(localdb)\MSSQLLocalDB' -d master -E -b -Q $q | Out-Null
if ($LASTEXITCODE -ne 0) {
    sqlcmd -S '(localdb)\MSSQLLocalDB' -d master -E -Q "IF DB_ID('$Database') IS NOT NULL ALTER DATABASE [$Database] SET MULTI_USER;" | Out-Null
    throw "The restore failed. Nothing is lost: the state before it is saved as $undo."
}
Write-Host "Restored '$Name'. The state before the restore is saved as '$undo'." -ForegroundColor Green
Write-Host 'Now run START.cmd to start PesoWeb again.'
