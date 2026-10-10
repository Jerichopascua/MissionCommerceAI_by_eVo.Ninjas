# Stops PesoWeb (port 5071), the screens (4200) and the dashboard (8080). Your data is not touched.
foreach ($port in 5071, 4200, 8080) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "  port $port : nothing running"; continue }
    foreach ($c in $conns) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue }
    Write-Host "  port $port : stopped"
}
