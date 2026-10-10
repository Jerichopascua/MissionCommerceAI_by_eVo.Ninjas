# Starts everything the demo needs, each in its own minimised window, and waits until each answers.
#
#   powershell -ExecutionPolicy Bypass -File ui\demo\start-demo.ps1
#
# PesoWeb (API) on 5071, the PesoWeb screens (Angular) on 4200, the AI dashboard and explainer on 8080.
# It does not start the agent runner: run   python -m simpeso.agent_service --run real2 --company c1 --interval 30   in sim\  when you want Run now to work.
# Needs: SQL Server LocalDB with the PesoWeb_MissionDev database, Node, Python and the .NET SDK.
param(
    [string]$PesoWeb = 'D:\git\Retailo_v1_mission',
    [string]$Database = 'PesoWeb_MissionDev'
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$conn = "Server=(localdb)\MSSQLLocalDB;Database=$Database;Trusted_Connection=True;TrustServerCertificate=True;MultipleActiveResultSets=true"

function Test-Port($port) { [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }

function Wait-Url($url, $name, $seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri $url -Headers @{ Accept = 'text/html' } -TimeoutSec 5 -ErrorAction Stop
            if ($r.StatusCode -lt 500) { Write-Host "  $name is up: $url"; return }
        } catch {
            if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -lt 500) { Write-Host "  $name is up: $url"; return }
        }
        Start-Sleep -Seconds 3
    }
    Write-Warning "$name did not answer within $seconds seconds ($url)"
}

Write-Host 'Starting the demo...'

if (-not (Test-Port 5071)) {
    $env:ConnectionStrings__default = $conn
    $env:Snapshots__Enabled = 'true'          # test snapshots (save / restore of the whole demo database); off everywhere else
    if (-not $env:Snapshots__Folder) { $env:Snapshots__Folder = 'D:\PesoWeb_Snapshots' }   # never drive C
    Start-Process -WindowStyle Minimized -WorkingDirectory $PesoWeb -FilePath 'dotnet' -ArgumentList 'run', '--project', 'Retailo.csproj', '--no-build', '--no-launch-profile', '--urls', 'http://localhost:5071'
} else { Write-Host '  PesoWeb is already running on 5071' }

if (-not (Test-Port 4200)) {
    $env:ASPNETCORE_URLS = 'http://localhost:5071'
    Start-Process -WindowStyle Minimized -WorkingDirectory (Join-Path $PesoWeb 'ClientApp') -FilePath 'cmd.exe' -ArgumentList '/c', 'npx ng serve --port 4200 --host 127.0.0.1 --proxy-config proxy.conf.js'
} else { Write-Host '  The PesoWeb screens are already running on 4200' }

if (-not (Test-Port 8080)) {
    Start-Process -WindowStyle Minimized -WorkingDirectory $repo -FilePath 'python' -ArgumentList '-m', 'http.server', '8080', '--bind', '127.0.0.1'
} else { Write-Host '  The dashboard server is already running on 8080' }

Wait-Url 'http://127.0.0.1:8080/ui/hub/index.html' 'Dashboard and explainer' 30
Wait-Url 'http://localhost:5071/api/ai/settings' 'PesoWeb API' 120
Write-Host '  The PesoWeb screens take a minute or two to compile the first time...'
Wait-Url 'http://127.0.0.1:4200/' 'PesoWeb screens' 240

Write-Host ''
Write-Host 'Open these:'
Write-Host '  PesoWeb screens        http://127.0.0.1:4200            (log in; logins are in sim\runs\CREDENTIALS.txt)'
Write-Host '  Intelligence Hub       http://127.0.0.1:4200/#/ai/hub'
Write-Host '  Explainer page         http://127.0.0.1:8080/ui/hub/index.html'
Write-Host '  AI results dashboard   http://127.0.0.1:8080/ui/dashboard/index.html'
