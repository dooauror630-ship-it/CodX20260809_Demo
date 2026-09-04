param(
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
if ($env:AGRI_DATABASE_ENGINE -ne "mysql") { throw "Migration drills require AGRI_DATABASE_ENGINE=mysql." }
if ([string]::IsNullOrWhiteSpace($env:AGRI_MYSQL_DATABASE) -or -not $env:AGRI_MYSQL_DATABASE.EndsWith("_test", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Migration drills require AGRI_MYSQL_DATABASE to end in _test."
}
& (Join-Path $PSScriptRoot "verify-backup.ps1") -BackupFile $BackupFile
Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = "."
    python -m flask --app backend.wsgi:app db upgrade
    if ($LASTEXITCODE -ne 0) { throw "Alembic upgrade failed." }
    python -m flask --app backend.wsgi:app schema-check
    if ($LASTEXITCODE -ne 0) { throw "Schema check failed." }
    python -m flask --app backend.wsgi:app inventory-reconcile
    if ($LASTEXITCODE -ne 0) { throw "Inventory reconciliation failed." }
    python -m flask --app backend.wsgi:app trade-reconcile
    if ($LASTEXITCODE -ne 0) { throw "Trade reconciliation failed." }
} finally {
    Pop-Location
}
Write-Host "MySQL migration drill passed for test database '$env:AGRI_MYSQL_DATABASE'." -ForegroundColor Green
