# End-to-end check of Plan 3 through the real API: batch cost, cash refund on a sale return, exceptions,
# stock count, receiving discrepancy, and the root-only group overview refusing a normal tenant owner.
# Creates its own tenant, so it is safe to run repeatedly on a DEV database.
param([string] $BaseUrl = 'http://localhost:5061')
$u = $BaseUrl                               # seed-expiry-tenant.ps1 has its own $BaseUrl parameter; keep ours
. "$PSScriptRoot\seed-expiry-tenant.ps1"    # also loads common.ps1

function Assert-True($cond, $what) { if (-not $cond) { throw "FAIL $what" } ; Write-Host "OK   $what" }

$run = 'plan3-smoke-' + [guid]::NewGuid().ToString('N').Substring(0, 8)

# 0. A fresh owner with an expiry-tracked product and a received batch (cost 60, price 100, expires in 3 days)
$w = New-ExpiryTenant -BaseUrl $u -Prefix 'plan3' -ExpiresInDays 3 -Qty 20 -Cost 60 -Price 100 -SimRun $run
$t = $w.Token; $wh = $w.WarehouseId; $pid2 = $w.ProductId
Write-Host "Seeded tenant $($w.TenantID): branch $wh, product $pid2, purchase $($w.PurchaseId)"

# 1. Task 2: the purchase cost reached the batch (it used to be NULL)
$ne = Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path "/api/Inventory/NearExpiryBatches?warehouse=$wh&pageSize=50"
$batch = @($ne.data | Where-Object { $_.productId -eq $pid2 }) | Select-Object -First 1
Assert-True ($batch -and [decimal]$batch.cost -eq 60) "batch cost stored from the purchase (cost = $($batch.cost))"

# 2. Task 3: a cash sale, a return, and the refund on the open shift
$shift = Invoke-PesoApi -BaseUrl $u -Token $t -Method POST -Path '/api/CashShifts/Open' -SimRun $run -Body @{ warehouseId = $wh; posTerminal = 'POS-01'; openingCash = 1000 }
$cust = (Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path '/api/People/Customers?page=1&pageSize=5').data | Select-Object -First 1
$sale = Invoke-PesoForm $u $t '/api/Sales/AddSale' @{
    warehouseId = $wh; customerId = $cust.id; discountPercentage = 0; taxPercentage = 0; shippingCharges = 0
    paidAmount = 100; paymentMethod = 'Cash'; orderStatus = 1
    'saleDetails[0].productId' = $pid2; 'saleDetails[0].quantity' = 1
} $run
Assert-True ([decimal]$sale.totalAmount -eq 100) "cash sale made (total $($sale.totalAmount))"
$ret = Invoke-PesoForm $u $t '/api/Sales/AddReturn' @{
    SaleId = $sale.id; WarehouseId = $wh; CustomerId = $cust.id; SaleReturnDate = (Get-Date).ToString('yyyy-MM-dd'); TaxPercentage = 0
    'saleReturnDetails[0].productId' = $pid2; 'saleReturnDetails[0].quantity' = 1
} $run
Assert-True ([decimal]$ret.totalAmount -eq 100) "sale return made (total $($ret.totalAmount))"
$cur = Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path "/api/CashShifts/Current?warehouseId=$wh"
Assert-True ([decimal]$cur.summary.cashRefunds -eq 100) "cash refund recorded on the open shift (refunds $($cur.summary.cashRefunds))"
Assert-True ([decimal]$cur.summary.expectedCash -eq 1000) "expected cash = 1000 + 100 sale - 100 refund (got $($cur.summary.expectedCash))"
$ev = Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path "/api/ai/events?simRunId=$run&take=1000"
$returned = @($ev.events | Where-Object { $_.eventType -eq 'SaleReturned' })
Assert-True ($returned.Count -eq 1 -and $returned[0].payload.refundRecorded -eq $true) 'SaleReturned event published with refundRecorded = true'

# 3. Task 4: closing the shift short raises a CASH_VARIANCE exception
$closed = Invoke-PesoApi -BaseUrl $u -Token $t -Method POST -Path '/api/CashShifts/Close' -SimRun $run -Body @{ shiftId = $shift.id; actualCash = 950; note = 'smoke' }
Assert-True ([decimal]$closed.variance -eq -50) "shift closed with variance $($closed.variance)"
$cv = @(Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path "/api/Exceptions/List?warehouseId=$wh&status=Open&type=CASH_VARIANCE")
Assert-True ($cv.Count -eq 1 -and $cv[0].severity -eq 'Medium') 'CASH_VARIANCE exception recorded (Medium)'

# 4. Task 4: detection finds the expiry alert and is idempotent
$d1 = Invoke-PesoApi -BaseUrl $u -Token $t -Method POST -Path "/api/Exceptions/Detect?warehouseId=$wh" -SimRun $run
Assert-True ($d1.added -ge 1) "detect added $($d1.added) exception(s)"
$alerts = @(Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path "/api/Exceptions/List?warehouseId=$wh&type=EXPIRY_ALERT")
Assert-True ($alerts.Count -eq 1) 'EXPIRY_ALERT exception for the batch expiring in 3 days'
$d2 = Invoke-PesoApi -BaseUrl $u -Token $t -Method POST -Path "/api/Exceptions/Detect?warehouseId=$wh" -SimRun $run
Assert-True ($d2.added -eq 0) 'detect is idempotent (second run added 0)'
$aiEx = Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path '/api/ai/exceptions?afterId=0&take=100'
Assert-True (@($aiEx.exceptions).Count -ge 2) '/api/ai/exceptions answers'

# 5. Task 5: stock count finds 2 missing units, posts through FEFO, and the ledger stays consistent
$sc = Invoke-PesoApi -BaseUrl $u -Token $t -Method POST -Path '/api/StockCounts/Create' -SimRun $run -Body @{ warehouseId = $wh; productIds = @($pid2); note = 'smoke count' }
$line = @($sc.lines)[0]
Assert-True ([decimal]$line.systemQty -eq 20) "stock count snapshot system qty = $($line.systemQty)"
Invoke-PesoApi -BaseUrl $u -Token $t -Method POST -Path '/api/StockCounts/Submit' -SimRun $run -Body @{ stockCountId = $sc.count.id; counts = @(@{ productId = $pid2; countedQty = 18; reason = 'damaged' }) } | Out-Null
$appr = Invoke-PesoApi -BaseUrl $u -Token $t -Method POST -Path '/api/StockCounts/Approve' -SimRun $run -Body @{ stockCountId = $sc.count.id }
Assert-True ([decimal]$appr.unitsAdjusted -eq 2 -and [decimal]$appr.pesosLost -eq 120) "stock count approved (units $($appr.unitsAdjusted), lost $($appr.pesosLost))"
$ne2 = Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path "/api/Inventory/NearExpiryBatches?warehouse=$wh&pageSize=50"
$batch2 = @($ne2.data | Where-Object { $_.productId -eq $pid2 }) | Select-Object -First 1
Assert-True ([decimal]$batch2.qtyOnHand -eq 18) "batch quantity now $($batch2.qtyOnHand)"
$scEx = @(Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path "/api/Exceptions/List?warehouseId=$wh&type=STOCK_COUNT_VARIANCE")
Assert-True ($scEx.Count -eq 1) 'STOCK_COUNT_VARIANCE exception recorded'
$drift = ConvertTo-List (Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path "/api/ai/ledger-drift?warehouseId=$wh")
Assert-True ($drift.Count -eq 0) "ledger and on-hand agree after the count (drift rows: $($drift.Count))"

# 6. Task 6: a short delivery is recorded against what was expected
$rep = Invoke-PesoApi -BaseUrl $u -Token $t -Method POST -Path '/api/Receiving/Report' -SimRun $run -Body @{
    warehouseId = $wh; sourceType = 'Purchase'; sourceId = $w.PurchaseId; productId = $pid2; expectedQty = 25; receivedQty = 20; note = 'driver short-delivered' }
Assert-True ($rep.status -eq 'Short' -and [decimal]$rep.difference -eq -5) "receiving report: $($rep.status), difference $($rep.difference)"
$short = @(Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path "/api/Exceptions/List?warehouseId=$wh&type=SUPPLIER_SHORT_SHIPMENT")
Assert-True ($short.Count -eq 1) 'SUPPLIER_SHORT_SHIPMENT exception recorded'
$aiRep = Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path '/api/ai/receiving-reports?afterId=0&take=100'
Assert-True (@($aiRep.reports).Count -ge 1) '/api/ai/receiving-reports answers'

# 7. Events for the whole run
$ev2 = Invoke-PesoApi -BaseUrl $u -Token $t -Method GET -Path "/api/ai/events?simRunId=$run&take=1000"
$types = @($ev2.events | ForEach-Object { $_.eventType })
foreach ($needed in 'CashOpened', 'SaleCompleted', 'SaleReturned', 'CashClosed', 'StockCountApproved', 'ReceivingReported') {
    Assert-True ($types -contains $needed) "event $needed published"
}

# 8. Task 7: the group overview is for the central company only. A tenant owner must be refused.
$code = & curl.exe -s -o NUL -w '%{http_code}' -H "Authorization: Bearer $t" "$u/api/Group/Overview"
Assert-True ($code -eq '403') "group overview refuses a tenant owner (HTTP $code)"

Write-Host 'ALL CHECKS PASSED'
