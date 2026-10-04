# Shared helpers for the PesoWeb smoke scripts. Verified against a live app on 2026-10-05.

function Invoke-PesoApi {
    param(
        [Parameter(Mandatory)] [string] $BaseUrl,
        [string] $Token,
        [Parameter(Mandatory)] [string] $Method,
        [Parameter(Mandatory)] [string] $Path,
        $Body,
        [string] $SimRun
    )
    $headers = @{}
    if ($Token)  { $headers['Authorization'] = "Bearer $Token" }
    if ($SimRun) { $headers['X-Sim-Run'] = $SimRun }
    $req = @{ Uri = "$BaseUrl$Path"; Method = $Method; Headers = $headers; ContentType = 'application/json' }
    if ($null -ne $Body) { $req['Body'] = ($Body | ConvertTo-Json -Depth 8) }
    try {
        return Invoke-RestMethod @req
    } catch {
        $detail = ''
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $detail = $reader.ReadToEnd()
        }
        throw "API $Method $Path failed: $($_.Exception.Message) $detail"
    }
}

# Windows PowerShell 5.1 hands back an empty JSON array [] as one wrapper object ({ value = @(); Count = 0 }),
# so @(...).Count would be 1. Use this to count list results reliably.
function ConvertTo-List {
    param($Value)
    $items = @($Value)
    if ($items.Count -eq 1) {
        if ($null -eq $items[0]) { return @() }
        if ($items[0].PSObject.Properties['value'] -and $items[0].PSObject.Properties['Count'] -and @($items[0].value).Count -eq 0) { return @() }
    }
    return $items
}

function New-SimTenant {
    param(
        [Parameter(Mandatory)] [string] $BaseUrl,
        [string] $Prefix = 'sim'
    )
    $id = [guid]::NewGuid().ToString('N').Substring(0, 10)
    $email = "$Prefix+$id@example.test"
    $password = "Sim!$id"
    $body = @{
        CompanyName = "$Prefix store $id"; FirstName = 'Sim'; LastName = 'Owner'
        Email = $email; Phone = '+639000000000'; Password = $password; ConfirmPassword = $password
    }
    $r = Invoke-PesoApi -BaseUrl $BaseUrl -Method POST -Path '/api/Auth/Register' -Body $body
    return [pscustomobject]@{
        Token = $r.token; TenantID = $r.tenantID; WarehouseId = $r.defaultWarehouseId
        Email = $email; Password = $password; Permissions = $r.permissions
    }
}
