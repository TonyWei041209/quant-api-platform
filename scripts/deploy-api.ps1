<#
.SYNOPSIS
    Deploy quant-api and auto-sync the T212 sync job image.

.DESCRIPTION
    1. Deploys quant-api to Cloud Run from source
    2. On success, syncs quant-sync-t212 job to the same image digest
    3. Verifies alignment

    If the API deploy fails, the job sync is skipped.
    If the job sync fails, the script exits with error (API is still deployed).

.PARAMETER Region
    GCP region. Default: asia-east2

.PARAMETER Memory
    Memory allocation. Default: 512Mi

.PARAMETER Timeout
    Request timeout. Default: 60

.PARAMETER SkipJobSync
    Deploy API only, skip job image sync.

.EXAMPLE
    .\scripts\deploy-api.ps1
    .\scripts\deploy-api.ps1 -SkipJobSync
#>
param(
    [string]$Region = "asia-east2",
    [string]$Memory = "512Mi",
    [int]$Timeout = 60,
    [switch]$SkipJobSync
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Quant API Platform — Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Deploy API
Write-Host "[1/3] Deploying quant-api to Cloud Run..." -ForegroundColor Yellow
Write-Host "  Region: $Region | Memory: $Memory | Timeout: ${Timeout}s"
Write-Host ""

# Note: gcloud writes progress to stderr. With $ErrorActionPreference="Stop",
# PowerShell treats stderr as terminating errors. Temporarily use "Continue".
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
gcloud run deploy quant-api `
    --source . `
    --region $Region `
    --allow-unauthenticated `
    --port 8080 `
    --memory $Memory `
    --timeout $Timeout
$deployExitCode = $LASTEXITCODE
$ErrorActionPreference = $prevEAP

if ($deployExitCode -ne 0) {
    Write-Host ""
    Write-Host "  ERROR: API deploy failed (exit code $deployExitCode). Job sync skipped." -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "  API deployed successfully." -ForegroundColor Green

# Step 2: Sync Job image
if ($SkipJobSync) {
    Write-Host ""
    Write-Host "[2/3] Job sync skipped (-SkipJobSync)." -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "[2/3] Syncing quant-sync-t212 job image..." -ForegroundColor Yellow

    $syncScript = Join-Path $ScriptDir "sync-job-image.ps1"
    if (-not (Test-Path $syncScript)) {
        Write-Host "  ERROR: sync-job-image.ps1 not found at $syncScript" -ForegroundColor Red
        Write-Host "  API was deployed but Job image NOT synced." -ForegroundColor Red
        Write-Host "  Run manually: .\scripts\sync-job-image.ps1" -ForegroundColor Yellow
        exit 1
    }

    try {
        & $syncScript -Region $Region
        if ($LASTEXITCODE -ne 0) {
            throw "sync-job-image.ps1 exited with code $LASTEXITCODE"
        }
    } catch {
        Write-Host ""
        Write-Host "  WARNING: Job image sync failed." -ForegroundColor Red
        Write-Host "  API was deployed but Job image NOT synced." -ForegroundColor Red
        Write-Host "  Run manually: .\scripts\sync-job-image.ps1" -ForegroundColor Yellow
        exit 1
    }
}

# Step 3: Final status
Write-Host ""
Write-Host "[3/3] Final verification..." -ForegroundColor Yellow
& (Join-Path $ScriptDir "sync-job-image.ps1") -CheckOnly -Region $Region
$aligned = ($LASTEXITCODE -eq 0)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deploy Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  API deploy    : SUCCESS" -ForegroundColor Green
if ($SkipJobSync) {
    Write-Host "  Job sync      : SKIPPED" -ForegroundColor Gray
} elseif ($aligned) {
    Write-Host "  Job sync      : SUCCESS" -ForegroundColor Green
    Write-Host "  Image aligned : YES" -ForegroundColor Green
} else {
    Write-Host "  Job sync      : DONE (alignment unconfirmed)" -ForegroundColor Yellow
}
Write-Host ""
