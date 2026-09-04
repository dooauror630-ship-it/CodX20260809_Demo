param(
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [Parameter(Mandatory = $true)][string]$TestDatabase
)

$ErrorActionPreference = "Stop"
if (-not $TestDatabase.EndsWith("_test", [System.StringComparison]::OrdinalIgnoreCase)) { throw "Restore drills require a database ending in _test." }
& (Join-Path $PSScriptRoot "verify-backup.ps1") -BackupFile $BackupFile
$mysql = Get-Command mysql -ErrorAction Stop
$gzip = Get-Command gzip -ErrorAction Stop
Get-Content -LiteralPath $BackupFile -Raw -Encoding Byte | & $gzip.Source -dc | & $mysql.Source $TestDatabase
if ($LASTEXITCODE -ne 0) { throw "MySQL restore drill failed." }
Write-Host "Restore drill completed against test database '$TestDatabase'." -ForegroundColor Green
