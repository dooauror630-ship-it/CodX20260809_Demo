param(
    [switch]$MySql,
    [switch]$E2E
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Push-Location $projectRoot
try {
    $testDatabase = [string]$env:AGRI_MYSQL_DATABASE
    if (($MySql -or $E2E) -and -not $testDatabase.EndsWith("_test")) {
        throw "MySQL and E2E tests require AGRI_MYSQL_DATABASE to end in '_test'."
    }

    python -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff failed." }

    python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }

    if ($MySql) {
        $previousRunMySqlTests = $env:AGRI_RUN_MYSQL_TESTS
        try {
            $env:AGRI_RUN_MYSQL_TESTS = "1"
            python -m pytest tests\test_mysql_integration.py -q
            if ($LASTEXITCODE -ne 0) { throw "MySQL integration tests failed." }
        } finally {
            $env:AGRI_RUN_MYSQL_TESTS = $previousRunMySqlTests
        }
    }

    if ($E2E) {
        $previousBootstrapPassword = $env:AGRI_BOOTSTRAP_ADMIN_PASSWORD
        try {
            $env:AGRI_BOOTSTRAP_ADMIN_PASSWORD = "123456"
            python -m flask --app backend.wsgi:app bootstrap-admin
            if ($LASTEXITCODE -ne 0) { throw "Test administrator bootstrap failed." }
        } finally {
            $env:AGRI_BOOTSTRAP_ADMIN_PASSWORD = $previousBootstrapPassword
        }
    }

    Push-Location (Join-Path $projectRoot "frontend")
    try {
        npm.cmd run lint
        if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }

        npm.cmd run test:unit
        if ($LASTEXITCODE -ne 0) { throw "Frontend unit tests failed." }

        npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }

        if ($E2E) {
            npm.cmd run test:e2e
            if ($LASTEXITCODE -ne 0) { throw "Browser E2E tests failed." }
        }
    } finally {
        Pop-Location
    }

    Write-Host "All requested checks passed." -ForegroundColor Green
} finally {
    Pop-Location
}
