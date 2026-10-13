param([switch]$Production)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$logPath = Join-Path $projectRoot '.logs'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Existing .venv not found.' }
if ($Production -and -not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\.next\standalone\server.js'))) {
    throw 'Production build missing. Run pnpm build in frontend first.'
}
foreach ($port in @(8000, 3000)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Stop the existing server before starting."
    }
}
New-Item -ItemType Directory -Path $logPath -Force | Out-Null
Push-Location (Join-Path $projectRoot 'backend')
try {
    & $pythonPath -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
} finally { Pop-Location }
$backend = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logPath 'backend.log') -RedirectStandardError (Join-Path $logPath 'backend-error.log')
if ($Production) {
    $previousPort = $env:PORT
    $previousBindHost = $env:HOSTNAME
    try {
        $env:PORT = '3000'
        $env:HOSTNAME = '127.0.0.1'
        $serverPath = Join-Path $projectRoot 'frontend\.next\standalone\server.js'
        $frontend = Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @("`"$serverPath`"") -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logPath 'frontend.log') -RedirectStandardError (Join-Path $logPath 'frontend-error.log')
    } finally {
        $env:PORT = $previousPort
        $env:HOSTNAME = $previousBindHost
    }
} else {
    $frontend = Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @('node_modules/next/dist/bin/next', 'dev', '--hostname', '127.0.0.1', '--port', '3000') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logPath 'frontend.log') -RedirectStandardError (Join-Path $logPath 'frontend-error.log')
}
@{backend=$backend.Id; frontend=$frontend.Id} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logPath 'processes.json')
foreach ($url in @('http://127.0.0.1:8000/api/v1/health', 'http://127.0.0.1:3000')) {
    $deadline = (Get-Date).AddSeconds(60)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        & $pythonPath (Join-Path $projectRoot 'scripts\check-ready.py') $url
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Milliseconds 300
    }
    if (-not $ready) { throw "Server did not become ready: $url. Inspect logs under $logPath." }
}
Write-Output 'ResearchLens AI: http://localhost:3000'
Write-Output 'API documentation: http://localhost:8000/docs'
Write-Output "Logs: $logPath"
