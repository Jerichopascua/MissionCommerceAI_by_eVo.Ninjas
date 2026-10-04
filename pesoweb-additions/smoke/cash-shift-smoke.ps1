# End-to-end check of the cash shift, event outbox and ledger endpoints through the real API.
# Verified against a live app on 2026-10-05: ALL CHECKS PASSED.
param([string] $BaseUrl = 'http://localhost:5061')
. "$PSScriptRoot\common.ps1"

function Assert-Equal($actual, $expected, $what) {
    if ([decimal]$actual -ne [decimal]$expected) { throw "FAIL $what : expected $expected, got $actual" }
    Write-Host "OK   $what = $actual"
}

$run = "smoke-" + [guid]::NewGuid().ToString('N').Substring(0, 8)
$t = New-SimTenant -BaseUrl $BaseUrl -Prefix 'cashsmoke'
$wh = $t.WarehouseId

# Cashier opens a shift with 1000 float
$shift = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method POST -Path '/api/CashShifts/Open' -SimRun $run `
    -Body @{ warehouseId = $wh; posTerminal = 'POS-01'; openingCash = 1000 }
Write-Host "Opened shift $($shift.id)"

# A second open shift for the same cashier must be refused
$refused = $false
try {
    Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method POST -Path '/api/CashShifts/Open' -SimRun $run `
        -Body @{ warehouseId = $wh; posTerminal = 'POS-02'; openingCash = 50 } | Out-Null
} catch { $refused = $true }
if (-not $refused) { throw 'FAIL second open shift should have been refused' }
Write-Host 'OK   second open shift refused'

# Cash in 200, count 1150 -> expected 1200, variance -50
Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method POST -Path '/api/CashShifts/AddMovement' -SimRun $run `
    -Body @{ shiftId = $shift.id; movementType = 'CashIn'; amount = 200; reason = 'float top-up' } | Out-Null

$current = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method GET -Path "/api/CashShifts/Current?warehouseId=$wh"
Assert-Equal $current.summary.expectedCash 1200 'expected cash before close'

$closed = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method POST -Path '/api/CashShifts/Close' -SimRun $run `
    -Body @{ shiftId = $shift.id; actualCash = 1150; note = 'smoke' }
Assert-Equal $closed.expectedCash 1200 'closed expected cash'
Assert-Equal $closed.variance -50 'closed variance'

# Events for this run must include CashOpened and CashClosed
$ev = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method GET -Path "/api/ai/events?simRunId=$run"
$types = @($ev.events | ForEach-Object { $_.eventType })
if (($types -notcontains 'CashOpened') -or ($types -notcontains 'CashClosed')) { throw "FAIL events missing, got: $($types -join ',')" }
Write-Host "OK   events tagged $run : $($types -join ', ')"

# Shift shows up in the AI read API with its variance
$shifts = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method GET -Path "/api/ai/cash-shifts?warehouseId=$wh&closedOnly=true"
$mine = @($shifts) | Where-Object { $_.id -eq $shift.id }
Assert-Equal $mine.variance -50 'ai/cash-shifts variance'

# Ledger drift endpoint answers (empty for a fresh tenant)
$drift = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method GET -Path "/api/ai/ledger-drift?warehouseId=$wh"
Write-Host "OK   ledger-drift rows: $(@($drift).Count)"

Write-Host 'ALL CHECKS PASSED'
