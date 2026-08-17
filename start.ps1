param(
    [string]$NginxExe = $env:AGRI_NGINX_EXE
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $projectRoot "logs"
$nginxRoot = Join-Path $projectRoot "nginx"
$frontendIndex = Join-Path $projectRoot "frontend\dist\index.html"

if (-not $NginxExe) {
    $localNginx = Join-Path $nginxRoot "nginx.exe"
    $exampleNginx = "D:\PythonDemo\chapter2\nginx-1.31.3\nginx-1.31.3\nginx.exe"
    $NginxExe = if (Test-Path -LiteralPath $localNginx) { $localNginx } else { $exampleNginx }
}

if (-not (Test-Path -LiteralPath $NginxExe)) {
    throw "nginx.exe was not found. Pass its path with -NginxExe."
}
if (-not (Test-Path -LiteralPath $frontendIndex)) {
    throw "Frontend build was not found. Run 'npm.cmd run build' in the frontend directory."
}

$pythonCommand = Get-Command python -ErrorAction Stop
$nginxDirectories = @(
    (Join-Path $nginxRoot "logs"),
    (Join-Path $nginxRoot "temp\client_body_temp"),
    (Join-Path $nginxRoot "temp\proxy_temp"),
    (Join-Path $nginxRoot "temp\fastcgi_temp"),
    (Join-Path $nginxRoot "temp\uwsgi_temp"),
    (Join-Path $nginxRoot "temp\scgi_temp")
)
$runtimeDirectories = @($runtimeDir) + $nginxDirectories
New-Item -ItemType Directory -Force -Path $runtimeDirectories | Out-Null

foreach ($port in 5000, 8080) {
    if (netstat -ano | Select-String -Pattern "^\s*TCP\s+\S+:$port\s+\S+\s+LISTENING\s+\d+") {
        throw "Port $port is already in use."
    }
}

$backendProcess = $null
try {
    $backendProcess = Start-Process -FilePath $pythonCommand.Source `
        -ArgumentList @("-m", "waitress", "--host=127.0.0.1", "--port=5000", "backend.wsgi:app") `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeDir "backend.out.log") `
        -RedirectStandardError (Join-Path $runtimeDir "backend.error.log") `
        -PassThru
    Set-Content -LiteralPath (Join-Path $runtimeDir "backend.pid") -Value $backendProcess.Id

    $backendReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health" -TimeoutSec 1
            if ($health.success) {
                $backendReady = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 200
        }
    }
    if (-not $backendReady) {
        throw "Waitress failed to start. Check logs\backend.error.log."
    }

    $nginxPrefix = $nginxRoot + "\"
    & $NginxExe -p $nginxPrefix -c conf/nginx.conf -t
    if ($LASTEXITCODE -ne 0) {
        throw "The Nginx configuration test failed."
    }
    Start-Process -FilePath $NginxExe `
        -ArgumentList @("-p", $nginxPrefix, "-c", "conf/nginx.conf") `
        -WorkingDirectory $nginxRoot `
        -WindowStyle Hidden | Out-Null

    $pageReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $page = Invoke-WebRequest -Uri "http://127.0.0.1:8080" -TimeoutSec 1 -UseBasicParsing
            if ($page.StatusCode -eq 200) {
                $pageReady = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 200
        }
    }
    if (-not $pageReady) {
        throw "The Nginx page check failed."
    }

    Write-Host "System started: http://localhost:8080" -ForegroundColor Green
} catch {
    & $NginxExe -p ($nginxRoot + "\") -c conf/nginx.conf -s quit 2>$null
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    throw
}
