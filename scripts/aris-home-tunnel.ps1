# Publish localhost FastAPI through a free Cloudflare quick tunnel.
# The Worker at https://aris.anass-nadeem42.workers.dev proxies /api here.
#
# ASCII only so Windows PowerShell 5.1 can parse this file.
# Leave this window open. Leave the Legion plugged in.

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$LogDir = Join-Path $Root "cache"
$Worker = "https://aris.anass-nadeem42.workers.dev"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Wait-HttpOk {
    param([string]$Url, [int]$Seconds = 90)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
                return $true
            }
        } catch {
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Test-PortListening {
    param([int]$Port)
    try {
        $rows = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return [bool]$rows
    } catch {
        return $false
    }
}

function Start-ArisUvicorn {
    if (-not (Test-Path $Python)) {
        throw "Missing $Python - create the ARIS venv first."
    }
    $src = Join-Path $Root "src"
    $deps = Join-Path $Root ".deps"
    $env:PYTHONPATH = "$src;$Root;$deps"
    $uvOut = Join-Path $LogDir "uvicorn.out.log"
    $uvErr = Join-Path $LogDir "uvicorn.err.log"
    Start-Process -FilePath $Python -ArgumentList "-m","uvicorn","backend.main:app","--host","127.0.0.1","--port","8765" -WorkingDirectory $Root -RedirectStandardOutput $uvOut -RedirectStandardError $uvErr -WindowStyle Minimized
}

function Stop-PortListeners {
    param([int]$Port)
    try {
        $pids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($procId in $pids) {
            if ($procId -and $procId -ne 0) {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
    }
}

Write-Host "Keeping the PC awake on AC power."
powercfg -change -standby-timeout-ac 0 | Out-Null
powercfg -change -hibernate-timeout-ac 0 | Out-Null
powercfg -change -monitor-timeout-ac 0 | Out-Null
# 0 = Do nothing. Closing the Legion lid will no longer kill the API on AC power.
powercfg -SETACVALUEINDEX SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 | Out-Null
powercfg -SETACTIVE SCHEME_CURRENT | Out-Null
Write-Host "Lid close on AC is now Do nothing."

$healthy = Wait-HttpOk "http://127.0.0.1:8765/health" 8
if (-not $healthy) {
    Stop-PortListeners -Port 8765
    Start-Sleep -Seconds 1
    Write-Host "Starting uvicorn on 127.0.0.1:8765"
    Start-ArisUvicorn
} else {
    Write-Host "uvicorn already healthy on 8765"
}

if (-not (Wait-HttpOk "http://127.0.0.1:8765/health" 120)) {
    throw "uvicorn did not become healthy. See cache\uvicorn.err.log"
}
Write-Host "FastAPI is up."

$cfOut = Join-Path $LogDir "cloudflared.out.log"
$cfErr = Join-Path $LogDir "cloudflared.err.log"
Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1
Set-Content -Path $cfOut -Value "" -Encoding ASCII
Set-Content -Path $cfErr -Value "" -Encoding ASCII

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    throw "cloudflared is not on PATH."
}

Write-Host "Opening Cloudflare quick tunnel..."
Start-Process -FilePath $cloudflared.Source -ArgumentList "tunnel","--url","http://127.0.0.1:8765","--no-autoupdate" -RedirectStandardOutput $cfOut -RedirectStandardError $cfErr -WindowStyle Hidden

$origin = $null
for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 2
    foreach ($log in @($cfErr, $cfOut)) {
        if (-not (Test-Path $log)) { continue }
        $text = Get-Content -Path $log -Raw -ErrorAction SilentlyContinue
        if ($text -match "https://[a-z0-9-]+\.trycloudflare\.com") {
            $origin = $Matches[0]
            break
        }
    }
    if ($origin) { break }
}
if (-not $origin) {
    throw "cloudflared did not print a trycloudflare URL. See cache\cloudflared.err.log"
}

Write-Host "Tunnel: $origin"
Set-Location $Root

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    $nodeGuess = Join-Path $env:ProgramFiles "nodejs\node.exe"
    if (Test-Path $nodeGuess) {
        $env:PATH = "$(Split-Path $nodeGuess);$env:PATH"
    }
}

$wranglerJs = Join-Path $Root "node_modules\wrangler\bin\wrangler.js"
if (Test-Path $wranglerJs) {
    $origin | & node $wranglerJs secret put API_ORIGIN --name aris
} else {
    $origin | npx --yes wrangler secret put API_ORIGIN --name aris
}
if ($LASTEXITCODE -ne 0) {
    throw "Failed to set API_ORIGIN on the Worker"
}

Write-Host "Checking $Worker/api/health"
if (Wait-HttpOk ($Worker + "/api/health") 60) {
    Write-Host "Live: $Worker"
} else {
    Write-Host "Tunnel is up. Wait about 15s and refresh the site."
}

Write-Host ""
Write-Host "Leave this window open. FastAPI and the tunnel die if you close it or the PC sleeps."
Write-Host "After a reboot, double-click scripts\aris-home-tunnel.cmd"
try {
    while ($true) {
        Start-Sleep -Seconds 15
        if (-not (Wait-HttpOk "http://127.0.0.1:8765/health" 4)) {
            Write-Host "uvicorn is down - restarting on 8765"
            Stop-PortListeners -Port 8765
            Start-Sleep -Seconds 1
            Start-ArisUvicorn
        }
    }
} finally {
    Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
}
