param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$frontendIndex = Join-Path $ProjectRoot "frontend\dist\index.html"
$wsgi = Join-Path $ProjectRoot "backend\wsgi.py"
if (-not (Test-Path -LiteralPath $frontendIndex)) { throw "Frontend build is missing: $frontendIndex" }
if (-not (Test-Path -LiteralPath $wsgi)) { throw "Backend entrypoint is missing: $wsgi" }

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = "."
    python -m compileall -q backend/app
    ruff check backend tests
    pytest -q
    npm.cmd --prefix frontend run build
} finally {
    Pop-Location
}
Write-Host "Release checks passed. Formal database migration remains an explicit deployment action." -ForegroundColor Green
