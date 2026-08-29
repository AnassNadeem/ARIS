# Start the ARIS FastAPI broker in this window (port 8765).
# ASCII only so Windows PowerShell 5.1 can parse this file.
# Leave the window open. Ctrl+C stops it.

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Missing $Python - create the ARIS venv first."
}

$src = Join-Path $Root "src"
$deps = Join-Path $Root ".deps"
$env:PYTHONPATH = "$src;$Root;$deps"
Set-Location $Root

# Stale uvicorn keeps 8765 bound; Ctrl+C in this window does not always kill it.
# Without this, a new start logs "Application startup complete" then Errno 10048
# and the old process (without new routes) keeps serving 404s.
foreach ($line in (netstat -ano)) {
    if ($line -match "127\.0\.0\.1:8765\s+.*LISTENING\s+(\d+)") {
        $listenPid = [int]$Matches[1]
        Write-Host "Port 8765 already in use by PID $listenPid - stopping it."
        Stop-Process -Id $listenPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

Write-Host "ARIS backend: http://127.0.0.1:8765/health"
Write-Host "Ctrl+C to stop."
& $Python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
