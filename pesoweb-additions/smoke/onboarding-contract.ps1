# Verifies the signup-to-branch part of the onboarding chain and lists the routes the simulator driver needs.
# NOT YET RUN against a live app (SQL Server was stopped when written). Run it, then finish docs/onboarding-contract.md.
param([string] $BaseUrl = 'http://localhost:5061')
. "$PSScriptRoot\common.ps1"

$t = New-SimTenant -BaseUrl $BaseUrl -Prefix 'contract'
Write-Host "Registered tenant $($t.TenantID), default warehouse $($t.WarehouseId)"
if (-not $t.Token)       { throw 'Register did not return a token' }
if (-not $t.WarehouseId) { throw 'Register did not return a default warehouse id' }

# Second branch through the real endpoint (bounded by the tier limit; a fresh tenant should be on the entry tier)
try {
    $wh = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method POST -Path '/api/Settings/AddWarehouse' -Body @{
        WarehouseName = 'Contract Branch 2'; Email = 'b2@example.test'; Phone = '+639000000001'
        Address = '1 Test St'; City = 'Manila'; State = 'NCR'; PostalCode = '1000'; Country = 'PH'
    }
    Write-Host "AddWarehouse OK: id $($wh.id)"
} catch {
    Write-Host "AddWarehouse refused (expected on a 1-branch tier): $_"
}

# Discover the routes the driver will need
$swagger = Invoke-RestMethod -Uri "$BaseUrl/swagger/v1/swagger.json" -Method GET
$swagger.paths.PSObject.Properties.Name |
    Where-Object { $_ -match '/(AddUser|AddProduct|Categories|Brands|Units|TaxRates|PaymentMethods|AddPurchase|AddSale|CashShifts|Pricing|Expiry)|/api/ai/' } |
    Sort-Object | ForEach-Object { Write-Host "ROUTE $_" }
