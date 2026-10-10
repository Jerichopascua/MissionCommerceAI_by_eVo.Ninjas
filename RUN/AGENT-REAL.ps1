# Starts the AI helper for the REAL company, so the "Run now" buttons work. Leave this window open while you test. Ctrl+C stops it.
# It asks for the password of the login (nothing is shown while you type; it is never saved).
#   RUN\AGENT-REAL.cmd
#   powershell -File RUN\AGENT-REAL.ps1 -Email other@login.com -AsOf ''     (-AsOf '' means: look at the last 28 days up to today)
param(
    [string]$Email = 'superuser@520minimart.test',
    [string]$AsOf = '2026-05-30',       # 520 Minimart's real sales end on this date; leave empty once there are sales from today
    [int]$Interval = 20,
    [switch]$Once
)
Set-Location (Join-Path (Split-Path -Parent $PSScriptRoot) 'sim')
$argv = @('-m', 'simpeso.agent_service', '--real', '--email', $Email, '--interval', $Interval)
if ($AsOf) { $argv += @('--as-of', $AsOf) }
if ($Once) { $argv += '--once' }
python @argv
