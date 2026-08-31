# ARIS overnight Playwright regression (ghost start, DNF tower, disappearing dots).
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/overnight_test.ps1
#
# Leaves the Next dev server running so you can inspect the UI after the run.

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $RepoRoot "frontend-next"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ReportDir = Join-Path $Frontend "e2e\reports"
$ReportHtml = Join-Path $ReportDir "overnight_$Timestamp.html"

Write-Host "=== ARIS overnight test $Timestamp ==="
Write-Host "Frontend: $Frontend"

if (-not (Test-Path $ReportDir)) {
  New-Item -ItemType Directory -Path $ReportDir | Out-Null
}

# Same-origin path. next.config rewrites /r2replay → the public R2 bucket when
# frontend-next/public/r2replay is not present. Do not use http://127.0.0.1:3000
# (CORS-fails when the tab is opened at http://localhost:3000).
$env:NEXT_PUBLIC_R2_BASE_URL = "/r2replay"
$envLocal = Join-Path $Frontend ".env.local"
$r2Line = "NEXT_PUBLIC_R2_BASE_URL=/r2replay"
if (-not (Test-Path $envLocal)) {
  Set-Content -Path $envLocal -Value $r2Line -Encoding ascii
} elseif (-not (Select-String -Path $envLocal -Pattern "NEXT_PUBLIC_R2_BASE_URL" -Quiet)) {
  Add-Content -Path $envLocal -Value $r2Line
}

Write-Host "[1/4] Starting Next dev server (npm run dev) in background..."
$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCmd) { $npmCmd = Get-Command npm -ErrorAction Stop }
$devLog = Join-Path $ReportDir "devserver_$Timestamp.log"
$devErr = Join-Path $ReportDir "devserver_$Timestamp.err"
$dev = Start-Process -FilePath $npmCmd.Source -ArgumentList "run","dev" -WorkingDirectory $Frontend -PassThru -WindowStyle Hidden -RedirectStandardOutput $devLog -RedirectStandardError $devErr
Write-Host "Dev server PID: $($dev.Id)"

Write-Host "[2/4] Waiting 15 seconds for the server to start..."
Start-Sleep -Seconds 15

Set-Location $Frontend
Write-Host "[3/4] Running Playwright: e2e/ghost_regression.spec.ts"
$playwrightExit = 0
try {
  npx playwright test e2e/ghost_regression.spec.ts --reporter=html
  $playwrightExit = $LASTEXITCODE
} catch {
  Write-Host "Playwright threw: $_"
  $playwrightExit = 1
}

$srcReport = Join-Path $Frontend "playwright-report\index.html"
if (Test-Path $srcReport) {
  Copy-Item -Path $srcReport -Destination $ReportHtml -Force
  $srcFolder = Join-Path $Frontend "playwright-report"
  $dstFolder = Join-Path $ReportDir "overnight_$Timestamp"
  Copy-Item -Path $srcFolder -Destination $dstFolder -Recurse -Force
  Write-Host "[4/4] HTML report copied to $ReportHtml"
} else {
  Write-Host "[4/4] No playwright-report/index.html found"
}

Write-Host ""
if ($playwrightExit -eq 0) {
  Write-Host "PASS"
} else {
  Write-Host "FAIL (playwright exit $playwrightExit)"
}
Write-Host "Dev server still running (PID $($dev.Id)) - not killed."
Write-Host "Inspect: http://localhost:3000"
exit $playwrightExit
