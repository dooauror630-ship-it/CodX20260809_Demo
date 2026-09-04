param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = "Stop"
$versions = Join-Path $ProjectRoot "backend\migrations\versions"
$revisions = @{}
foreach ($file in Get-ChildItem -LiteralPath $versions -Filter "*.py") {
    $content = Get-Content -LiteralPath $file.FullName -Raw
    $revision = [regex]::Match($content, 'revision\s*=\s*["'']([^"'']+)["'']').Groups[1].Value
    $down = [regex]::Match($content, 'down_revision\s*=\s*["'']([^"'']+)["'']').Groups[1].Value
    if ($revision) { $revisions[$revision] = $down }
}
$current = "0023_attachments"
$seen = [System.Collections.Generic.HashSet[string]]::new()
while ($current) {
    if (-not $seen.Add($current)) { throw "Migration cycle detected at $current" }
    if (-not $revisions.ContainsKey($current)) { throw "Missing migration revision $current" }
    $current = $revisions[$current]
}
if ($seen.Count -ne $revisions.Count) { throw "Migration graph contains an unconnected revision." }
Write-Host "Migration chain verified: $($seen.Count) revisions, latest 0023_attachments." -ForegroundColor Green
