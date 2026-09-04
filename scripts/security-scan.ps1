param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = "Stop"
Push-Location $ProjectRoot
try {
    $tracked = git ls-files
    $patterns = @('(^|/)(\.env|mysql\.json|secret_key)$', '\.(pem|key|p12)$', '(^|/)backups/', '(^|/)backend/instance/')
    $violations = @($tracked | Where-Object { $path = $_; $patterns | Where-Object { $path -match $_ } })
    if ($violations.Count -gt 0) { throw "Sensitive files are tracked: $($violations -join ', ')" }
} finally {
    Pop-Location
}
Write-Host "Repository security scan passed: no tracked secrets, private keys, backups, or runtime config." -ForegroundColor Green
