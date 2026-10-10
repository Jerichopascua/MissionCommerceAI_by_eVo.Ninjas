# Saves a safety copy of the whole database on drive D (never C). Asks for a name, or press Enter for an automatic one.
#   RUN\SAVE-SNAPSHOT.cmd                      (asks)
#   powershell -File RUN\SAVE-SNAPSHOT.ps1 -Name before-real-test
param(
    [string]$Name,
    [string]$Database = 'PesoWeb_MissionDev',
    [string]$Folder = 'D:\PesoWeb_Backups'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_structure.ps1')
if (-not $Name) { $Name = Read-Host 'Name for this safety copy (letters, digits, dash, underscore; press Enter for an automatic name)' }
if (-not $Name) { $Name = 'safety-' + (Get-Date -Format 'yyyyMMdd-HHmm') }
if ($Name -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$') { throw 'Use only letters, digits, dot, dash and underscore (at most 60 characters), starting with a letter or digit.' }
if (-not $Folder.StartsWith('D:', 'OrdinalIgnoreCase')) { throw 'Safety copies go on drive D, never C.' }
New-Item -ItemType Directory -Force $Folder | Out-Null
$file = Join-Path $Folder ($Name + '.bak')
if (Test-Path $file) { throw "A copy named '$Name' already exists ($file). Pick another name." }
$free = (Get-PSDrive D).Free
if ($free -lt 1GB) { throw ('Drive D has only {0} MB free; a copy needs about 250 MB plus room to spare. Free some space first.' -f [math]::Round($free / 1MB)) }
$structure = Get-DatabaseStructure -Database $Database
sqlcmd -S '(localdb)\MSSQLLocalDB' -d master -E -b -Q "BACKUP DATABASE [$Database] TO DISK = N'$file' WITH COPY_ONLY, INIT, CHECKSUM" | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $file)) { throw 'The backup failed. Is the database service running? Try:  sqllocaldb start MSSQLLocalDB' }
Set-Content -Path ($file -replace '\.bak$', '.structure.txt') -Value $structure -Encoding UTF8       # what the database looked like, so a restore can be checked
Write-Host ('Saved: {0}  ({1} MB)' -f $file, [math]::Round((Get-Item $file).Length / 1MB)) -ForegroundColor Green
