param(
    [string]$HealthUrl = "http://127.0.0.1:8080/api/health",
    [int]$Iterations = 20,
    [int]$P95Milliseconds = 1000
)
$ErrorActionPreference = "Stop"
$durations = @()
for ($i = 0; $i -lt $Iterations; $i++) {
    $elapsed = [System.Diagnostics.Stopwatch]::StartNew()
    $response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 5
    $elapsed.Stop()
    if (-not $response.success) { throw "Health endpoint returned an unsuccessful response." }
    $durations += $elapsed.Elapsed.TotalMilliseconds
}
$sorted = $durations | Sort-Object
$index = [Math]::Min($sorted.Count - 1, [Math]::Ceiling($sorted.Count * 0.95) - 1)
$p95 = [Math]::Round($sorted[$index], 1)
if ($p95 -gt $P95Milliseconds) { throw "Health P95 ${p95}ms exceeds ${P95Milliseconds}ms." }
Write-Host "Performance smoke passed: $Iterations requests, P95 ${p95}ms." -ForegroundColor Green
