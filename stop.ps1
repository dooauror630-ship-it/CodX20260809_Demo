param(
    [string]$NginxExe = $env:AGRI_NGINX_EXE
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nginxRoot = Join-Path $projectRoot "nginx"
$runtimeDir = Join-Path $projectRoot "logs"

if (-not $NginxExe) {
    $localNginx = Join-Path $nginxRoot "nginx.exe"
    $exampleNginx = "D:\PythonDemo\chapter2\nginx-1.31.3\nginx-1.31.3\nginx.exe"
    $NginxExe = if (Test-Path -LiteralPath $localNginx) { $localNginx } else { $exampleNginx }
}

if (Test-Path -LiteralPath $NginxExe) {
    & $NginxExe -p ($nginxRoot + "\") -c conf/nginx.conf -s quit 2>$null
}

$pidFile = Join-Path $runtimeDir "backend.pid"
if (Test-Path -LiteralPath $pidFile) {
    $backendPid = [int](Get-Content -LiteralPath $pidFile -Raw)
    $backendProcess = Get-Process -Id $backendPid -ErrorAction SilentlyContinue
    $backendCommandLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $backendPid" -ErrorAction SilentlyContinue).CommandLine
    if ($backendProcess -and $backendCommandLine -match "waitress" -and $backendCommandLine -match "backend\.wsgi:app") {
        Stop-Process -Id $backendPid -Force
    } elseif ($backendProcess) {
        Write-Warning "PID $backendPid does not belong to this project's Waitress process; it was not stopped."
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

Write-Host "System services stopped." -ForegroundColor Green
