# End-to-end check of guardrails, a markdown applied at the POS, events and the read APIs, through the real API.
# Verified against a live app on 2026-10-05: ALL CHECKS PASSED.
# DEV tenant only: it sets a pricing policy, creates a markdown, ends it, and creates TWO REAL SALES of 1 unit each.
param(
    [string] $BaseUrl = 'http://localhost:5061',
    [string] $Email = $env:PESOWEB_EMAIL,
    [string] $Password = $env:PESOWEB_PASSWORD,
    [switch] $Yes
)
. "$PSScriptRoot\common.ps1"

if (-not $Email -or -not $Password) { throw 'Set PESOWEB_EMAIL and PESOWEB_PASSWORD to a DEV tenant owner. Nothing is stored in the repo.' }
if (-not $Yes) { throw 'This script sets a pricing policy, creates a markdown and two real sales on the tenant you log in to. Re-run with -Yes on a DEV tenant.' }

# Raw HTTP helper that returns the status code (Invoke-RestMethod hides 202/422 details in PowerShell 5.1)
function Invoke-PesoStatus {
    param([string] $Method, [string] $Path, $Body, [string] $Token, [string] $SimRun)
    $tmp = [System.IO.Path]::GetTempFileName()
    try {
        $json = if ($null -ne $Body) { $Body | ConvertTo-Json -Depth 6 -Compress } else { '' }
        [System.IO.File]::WriteAllText($tmp, $json, (New-Object System.Text.UTF8Encoding $false))
        $curlArgs = @('-s', '-X', $Method, "$BaseUrl$Path", '-H', "Authorization: Bearer $Token", '-H', 'Content-Type: application/json', '-w', "`n%{http_code}")
        if ($SimRun) { $curlArgs += @('-H', "X-Sim-Run: $SimRun") }
        if ($null -ne $Body) { $curlArgs += @('--data-binary', "@$tmp") }
        $raw = & curl.exe @curlArgs
        $lines = @($raw)
        $status = [int]$lines[-1]
        $text = if ($lines.Count -gt 1) { ($lines[0..($lines.Count - 2)] -join "`n") } else { '' }
        $parsed = if ($text) { try { $text | ConvertFrom-Json } catch { $text } } else { $null }
        return [pscustomobject]@{ Status = $status; Body = $parsed }
    } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}

function Assert-True($cond, $what) { if (-not $cond) { throw "FAIL $what" } ; Write-Host "OK   $what" }

$run = 'pricing-smoke-' + [guid]::NewGuid().ToString('N').Substring(0, 8)

# 1. Login
$login = Invoke-PesoApi -BaseUrl $BaseUrl -Method POST -Path '/api/Auth/Login' -Body @{ Email = $Email; Password = $Password; IsRemember = $false }
$t = $login.token; $wh = $login.defaultWarehouseId
Assert-True ($t -and $wh) "logged in, default branch $wh"

# 2. Policy: autonomous within guardrails
$pol = Invoke-PesoStatus PUT '/api/Pricing/Policy' @{ hardMarginFloorPct = 5; softMarginFloorPct = 15; maxDiscountPct = 50; maxChangesPerSkuPerHour = 3; autonomyMode = 'Autonomous' } $t
Assert-True ($pol.Status -eq 200) 'policy saved (200)'

# 3. Find an expiry-tracked batch with stock
$ne = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/Inventory/NearExpiryBatches?warehouse=$wh&pageSize=50"
$batch = @($ne.data | Where-Object { $_.qtyOnHand -gt 0 }) | Select-Object -First 1
if (-not $batch) { throw 'No near-expiry batch with stock in this branch. Receive one first (see scripts/fefo_smoke_test_checklist.md in PesoWeb).' }
Write-Host "Using batch $($batch.id) product $($batch.productId) qty $($batch.qtyOnHand) cost $($batch.cost) expires $($batch.expiryDate)"

# 4. Product list price
$pd = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/Inventory/ProductDetail/$($batch.productId)?warehouse=$wh"
$price = if ($pd.price) { [decimal]$pd.price } elseif ($pd.product.price) { [decimal]$pd.product.price } else { 0 }
if ($price -le 0) { $pd | ConvertTo-Json -Depth 3; throw 'Could not read the product price from ProductDetail; adjust the property name in this script.' }
Write-Host "List price $price"

# 5. Guardrail: an absurd markdown must be refused (422) and recorded
$bad = Invoke-PesoStatus POST '/api/Pricing/Markdown' @{ warehouseId = $wh; productId = $batch.productId; batchId = $batch.id; newPrice = 0.01; reason = 'smoke: absurd'; source = 'Ai' } $t $run
Assert-True ($bad.Status -eq 422) "absurd markdown refused (422, code $($bad.Body.code))"

# 6. A sensible markdown (20% off) is applied, or waits for approval if it is under the soft floor
$newPrice = [math]::Round($price * 0.8, 2)
$m = Invoke-PesoStatus POST '/api/Pricing/Markdown' @{ warehouseId = $wh; productId = $batch.productId; batchId = $batch.id; newPrice = $newPrice; reason = 'smoke: 20% off'; source = 'Ai'; predictionRef = 'smoke-pred-1' } $t $run
if ($m.Status -eq 202) {
    Write-Host 'Needs approval (soft floor). Approving.'
    $a = Invoke-PesoStatus POST '/api/Pricing/Approve' @{ priceChangeId = $m.Body.priceChangeId } $t $run
    Assert-True ($a.Status -eq 200) 'approved (200)'
    $activeId = $a.Body.activeMarkdownId
} elseif ($m.Status -eq 200) {
    $activeId = $m.Body.activeMarkdownId
} else {
    throw "Markdown refused with $($m.Status) code $($m.Body.code): $($m.Body.message). Check the product's cost and price; the markdown must be a real discount above the hard floor."
}
Assert-True ($activeId -gt 0) "markdown active (id $activeId)"

$active = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/Pricing/Active?warehouseId=$wh"
Assert-True (@($active | Where-Object { $_.id -eq $activeId }).Count -eq 1) 'markdown listed in /api/Pricing/Active'

# 7. A real sale of 1 unit consumes FEFO and should be priced from the markdown
$cust = (Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path '/api/People/Customers?page=1&pageSize=5').data | Select-Object -First 1
if (-not $cust) { throw 'No customer found for the sale.' }
function New-SmokeSale([string] $label) {
    $out = & curl.exe -s -w "`n%{http_code}" -X POST "$BaseUrl/api/Sales/AddSale" -H "Authorization: Bearer $t" -H "X-Sim-Run: $run" `
        -F "warehouseId=$wh" -F "customerId=$($cust.id)" -F 'discountPercentage=0' -F 'taxPercentage=0' -F 'shippingCharges=0' `
        -F 'paidAmount=100000' -F 'paymentMethod=Cash' -F 'orderStatus=1' `
        -F "saleDetails[0].productId=$($batch.productId)" -F 'saleDetails[0].quantity=1'
    $lines = @($out); $status = [int]$lines[-1]
    if ($status -ne 201) { throw "AddSale ($label) returned $status : $($lines[0..($lines.Count - 2)] -join ' ')" }
    return ($lines[0..($lines.Count - 2)] -join "`n") | ConvertFrom-Json
}
$saleMd = New-SmokeSale 'markdown'
$mdUnit = [decimal]$saleMd.saleDetails[0].salePrice
Write-Host "Sale 1 unit price (markdown active): $mdUnit"

# 8. End the markdown; the next sale returns to the normal price
$end = Invoke-PesoStatus POST '/api/Pricing/End' @{ activeMarkdownId = $activeId; reason = 'smoke: end' } $t $run
Assert-True ($end.Status -eq 200) 'markdown ended (200)'
$saleNormal = New-SmokeSale 'normal'
$normalUnit = [decimal]$saleNormal.saleDetails[0].salePrice
Write-Host "Sale 2 unit price (no markdown): $normalUnit"
Assert-True ($mdUnit -lt $normalUnit) "markdown sale cheaper than normal ($mdUnit < $normalUnit)"

# 9. Events: two PriceChanged (markdown + restore) and two SaleCompleted, all tagged with this run
$ev = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/ai/events?simRunId=$run&take=1000"
$types = @($ev.events | ForEach-Object { $_.eventType })
Assert-True (@($types | Where-Object { $_ -eq 'PriceChanged' }).Count -ge 2) 'PriceChanged events published (markdown + restore)'
Assert-True (@($types | Where-Object { $_ -eq 'SaleCompleted' }).Count -eq 2) 'SaleCompleted events published'

# 10. Ledger and read APIs
$pc = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/Pricing/Changes?warehouseId=$wh"
$statuses = @($pc | ForEach-Object { $_.status })
Assert-True ($statuses -contains 'Rejected') 'ledger recorded the refused markdown'
Assert-True ($statuses -contains 'Ended') 'ledger recorded the restore'
$risk = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/Expiry/Risk?warehouseId=$wh"
Write-Host ("Expiry risk summaries: " + ($risk.summaries | ConvertTo-Json -Compress))
$aiRisk = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/ai/expiry-risk?warehouseId=$wh"
Assert-True ($null -ne $aiRisk.batches) '/api/ai/expiry-risk answers'
$chg = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path '/api/ai/price-changes?afterId=0&take=50'
Assert-True (@($chg.changes).Count -ge 3) '/api/ai/price-changes answers'

Write-Host 'ALL CHECKS PASSED'
