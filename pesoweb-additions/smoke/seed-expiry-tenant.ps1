# Does what a simulated owner does after signing up: category, brand, unit, tax rate, supplier,
# an expiry-tracked product, and a purchase receipt that creates a batch. Dot-source it, or run it to print the result.
#   . .\seed-expiry-tenant.ps1 ; $w = New-ExpiryTenant -BaseUrl http://localhost:5071
param([string] $BaseUrl = '', [int] $ExpiresInDays = 3, [decimal] $Qty = 20, [decimal] $Cost = 60, [decimal] $Price = 100)
. "$PSScriptRoot\common.ps1"

# multipart/form-data POST through curl.exe (Windows PowerShell 5.1 has no -Form)
function Invoke-PesoForm {
    param([string] $BaseUrl, [string] $Token, [string] $Path, [hashtable] $Fields, [string] $SimRun)
    $a = @('-s', '-X', 'POST', "$BaseUrl$Path", '-H', "Authorization: Bearer $Token")
    if ($SimRun) { $a += @('-H', "X-Sim-Run: $SimRun") }
    foreach ($k in $Fields.Keys) { $a += @('-F', "$k=$($Fields[$k])") }
    $a += @('-w', "`n%{http_code}")
    $lines = @(& curl.exe @a)
    $status = [int]$lines[-1]
    $text = if ($lines.Count -gt 1) { ($lines[0..($lines.Count - 2)] -join "`n") } else { '' }
    if ($status -lt 200 -or $status -ge 300) { throw "POST $Path -> $status : $text" }
    if ($text) { try { return $text | ConvertFrom-Json } catch { return $text } }
    return $null
}

function New-ExpiryTenant {
    param([string] $BaseUrl, [string] $Prefix = 'expiry', [int] $ExpiresInDays = 3, [decimal] $Qty = 20, [decimal] $Cost = 60, [decimal] $Price = 100, [string] $SimRun)
    $t = New-SimTenant -BaseUrl $BaseUrl -Prefix $Prefix
    $tok = $t.Token; $wh = $t.WarehouseId
    $id = [guid]::NewGuid().ToString('N').Substring(0, 6)

    $cat = Invoke-PesoForm $BaseUrl $tok '/api/Inventory/AddCategory' @{ CategoryName = 'Dairy' } $SimRun
    $brand = Invoke-PesoForm $BaseUrl $tok '/api/Inventory/AddBrand' @{ BrandName = 'Generic' } $SimRun
    $unit = Invoke-PesoApi -BaseUrl $BaseUrl -Token $tok -Method POST -Path '/api/Inventory/AddUnit' -SimRun $SimRun `
        -Body @{ unitName = 'Piece'; shortName = 'pc'; operator = '*'; operationValue = 1 }
    $tax = Invoke-PesoApi -BaseUrl $BaseUrl -Token $tok -Method POST -Path '/api/Settings/AddTaxRate' -SimRun $SimRun `
        -Body @{ taxName = 'No Tax'; taxPercentage = 0 }
    $sup = Invoke-PesoApi -BaseUrl $BaseUrl -Token $tok -Method POST -Path '/api/People/AddSupplier' -SimRun $SimRun `
        -Body @{ supplierName = "Supplier $id"; email = "s$id@example.test"; phone = '+639000000002'; address = '1 Supply St'; city = 'Manila'; state = 'NCR'; postalCode = '1000'; country = 'PH' }

    $product = Invoke-PesoForm $BaseUrl $tok '/api/Inventory/AddProduct' @{
        CategoryId = $cat.id; BrandId = $brand.id; UnitId = $unit.id; SaleUnitId = $unit.id; PurchaseUnitId = $unit.id
        TaxId = $tax.id; TaxMethod = 1; ProductCode = "MILK-$id"; BarcodeType = 'CODE128'; ProductName = "Fresh Milk $id"
        Cost = $Cost; Price = $Price; Discount = 0; StockAlert = 5
        MonitorExpiry = 'true'; BatchTracking = 'true'; ExpiryAlertDays = 30; HasVariants = 'false'
    } $SimRun

    $expiry = (Get-Date).Date.AddDays($ExpiresInDays).ToString('yyyy-MM-dd')
    $made = (Get-Date).Date.AddDays(-2).ToString('yyyy-MM-dd')
    $amount = $Qty * $Cost
    $purchase = Invoke-PesoForm $BaseUrl $tok '/api/Purchases/AddPurchase' @{
        WarehouseId = $wh; SupplierId = $sup.id; PurchaseDate = (Get-Date).ToString('yyyy-MM-dd')
        DiscountPercentage = 0; TaxPercentage = 0; ShippingCharges = 0; PaidAmount = $amount; OrderStatus = 1
        'purchaseDetails[0].productId' = $product.id; 'purchaseDetails[0].unitCost' = $Cost
        'purchaseDetails[0].quantity' = $Qty; 'purchaseDetails[0].amount' = $amount
        'purchaseDetails[0].batchNo' = "B-$id"; 'purchaseDetails[0].expiryDate' = $expiry; 'purchaseDetails[0].manufacturingDate' = $made
    } $SimRun

    return [pscustomobject]@{
        Email = $t.Email; Password = $t.Password; Token = $tok; TenantID = $t.TenantID; WarehouseId = $wh
        CategoryId = $cat.id; BrandId = $brand.id; UnitId = $unit.id; TaxId = $tax.id; SupplierId = $sup.id
        ProductId = $product.id; PurchaseId = $purchase.id; BatchNo = "B-$id"; ExpiryDate = $expiry; Qty = $Qty; Cost = $Cost; Price = $Price
    }
}

if ($BaseUrl) {
    $w = New-ExpiryTenant -BaseUrl $BaseUrl -ExpiresInDays $ExpiresInDays -Qty $Qty -Cost $Cost -Price $Price
    $w | Select-Object * -ExcludeProperty Token | ConvertTo-Json -Depth 3    # never print the access token
}
