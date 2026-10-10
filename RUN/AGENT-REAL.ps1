# Starts the AI helper for the REAL company, so the "Run now" buttons work for all five AI features that can run:
# AI Monitoring, AI Pricing, AI Product Loss Prevention, AI Replenish and AI Customer Mission.
# Leave this window open while you test. Ctrl+C stops it. It asks for the password of the login (nothing is shown while you type; never saved).
#   RUN\AGENT-REAL.cmd
#   powershell -File RUN\AGENT-REAL.ps1 -Email other@login.com -AsOf ''     (-AsOf '' means: look at the last 28 days up to today)
param(
    [string]$Email = 'superuser@520minimart.test',
    [string]$AsOf = '2026-05-30',       # 520 Minimart's real sales end on this date; leave empty once there are sales from today
    [int]$Interval = 20,
    [switch]$Once
)
if (-not (Get-NetTCPConnection -LocalPort 5071 -State Listen -ErrorAction SilentlyContinue)) {
    Write-Host 'PesoWeb is not running (nothing is listening on port 5071). Double-click START.cmd first, wait for "PesoWeb API is up", then run this again.' -ForegroundColor Red
    exit 2
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host 'Python was not found. Install Python 3 and run this again.' -ForegroundColor Red
    exit 2
}
Set-Location (Join-Path (Split-Path -Parent $PSScriptRoot) 'sim')
$argv = @('-m', 'simpeso.agent_service', '--real', '--email', $Email, '--interval', $Interval)
if ($AsOf) { $argv += @('--as-of', $AsOf) }
if ($Once) { $argv += '--once' }
python @argv
if ($LASTEXITCODE -ne 0 -and -not $Once) {
    Write-Host ''
    Write-Host 'The helper stopped. If it said 403 the login has no AI permission; if it said the password was wrong, run this again and retype it.' -ForegroundColor Yellow
}
