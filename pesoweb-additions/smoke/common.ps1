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
    $args = @{ Uri = "$BaseUrl$Path"; Method = $Method; Headers = $headers; ContentType = 'application/json' }
    if ($null -ne $Body) { $args['Body'] = ($Body | ConvertTo-Json -Depth 8) }
    try {
        return Invoke-RestMethod @args
    } catch {
        $detail = ''
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $detail = $reader.ReadToEnd()
        }
        throw "API $Method $Path failed: $($_.Exception.Message) $detail"
    }
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
