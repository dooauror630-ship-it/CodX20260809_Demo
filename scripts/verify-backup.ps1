param(
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [string]$ExpectedSha256
)

$ErrorActionPreference = "Stop"
$resolved = (Resolve-Path -LiteralPath $BackupFile).Path
$item = Get-Item -LiteralPath $resolved
if ($item.Length -le 0) { throw "Backup file is empty: $resolved" }
$hash = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
if ($ExpectedSha256 -and $hash -ne $ExpectedSha256.ToUpperInvariant()) { throw "Backup SHA256 mismatch. Expected $ExpectedSha256, got $hash." }
if ($resolved.EndsWith(".gz", [System.StringComparison]::OrdinalIgnoreCase)) {
    $gzip = [System.IO.File]::OpenRead($resolved)
    try { $stream = New-Object System.IO.Compression.GZipStream($gzip, [System.IO.Compression.CompressionMode]::Decompress); $buffer = New-Object byte[] 4096; while ($stream.Read($buffer, 0, $buffer.Length) -gt 0) {} } finally { if ($stream) { $stream.Dispose() }; $gzip.Dispose() }
}
Write-Host "Backup verified: $resolved ($hash)" -ForegroundColor Green
