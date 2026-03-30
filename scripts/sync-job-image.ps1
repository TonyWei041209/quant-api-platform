<#
.SYNOPSIS
    Sync Cloud Run Job image to match the main API service image.

.DESCRIPTION
    Reads the current container image from the quant-api Cloud Run service
    and updates the quant-sync-t212 Cloud Run Job to use the same image.
    Ensures both components run identical code.

    Does NOT use :latest tags. Uses explicit image digests for auditability.

.PARAMETER CheckOnly
    Only compare images without updating. Exit code 0 if aligned, 1 if mismatched.

.PARAMETER Region
    GCP region. Default: asia-east2

.PARAMETER ApiService
    Cloud Run service name. Default: quant-api

.PARAMETER JobName
    Cloud Run Job name. Default: quant-sync-t212

.EXAMPLE
    # Check alignment
    .\sync-job-image.ps1 -CheckOnly

    # Sync job to match API
    .\sync-job-image.ps1

    # Sync with custom names
    .\sync-job-image.ps1 -ApiService quant-api -JobName quant-sync-t212
#>
param(
    [switch]$CheckOnly,
    [string]$Region = "asia-east2",
    [string]$ApiService = "quant-api",
    [string]$JobName = "quant-sync-t212"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Cloud Run Image Alignment Check ===" -ForegroundColor Cyan
Write-Host "  API Service : $ApiService"
Write-Host "  Sync Job    : $JobName"
Write-Host "  Region      : $Region"
Write-Host ""

# Step 1: Get API service image
Write-Host "[1/4] Reading API service image..." -ForegroundColor Yellow
# Note: gcloud writes progress to stderr. With $ErrorActionPreference="Stop" and 2>&1,
# PowerShell treats stderr output as terminating errors. Use "Continue" for gcloud calls.
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$apiImage = gcloud run services describe $ApiService --region $Region --format 'value(spec.template.spec.containers[0].image)' 2>$null
$ErrorActionPreference = $prevEAP
if ($LASTEXITCODE -ne 0 -or -not $apiImage) {
    Write-Host "  ERROR: Could not read API service '$ApiService' in region '$Region'" -ForegroundColor Red
    Write-Host "  Check: gcloud run services list --region $Region" -ForegroundColor Gray
    exit 1
}
$apiImage = $apiImage.Trim()
Write-Host "  API: $apiImage" -ForegroundColor Green

# Step 2: Get Job image
Write-Host "[2/4] Reading Job image..." -ForegroundColor Yellow
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$jobImage = gcloud run jobs describe $JobName --region $Region --format 'value(spec.template.spec.template.spec.containers[0].image)' 2>$null
$ErrorActionPreference = $prevEAP
if ($LASTEXITCODE -ne 0 -or -not $jobImage) {
    Write-Host "  ERROR: Could not read Job '$JobName' in region '$Region'" -ForegroundColor Red
    Write-Host "  Check: gcloud run jobs list --region $Region" -ForegroundColor Gray
    exit 1
}
$jobImage = $jobImage.Trim()
Write-Host "  Job: $jobImage" -ForegroundColor Green

# Step 3: Compare
Write-Host ""
Write-Host "[3/4] Comparing images..." -ForegroundColor Yellow
if ($apiImage -eq $jobImage) {
    Write-Host ""
    Write-Host "  ALIGNED - Both use the same image." -ForegroundColor Green
    Write-Host ""
    exit 0
}

Write-Host "  MISMATCHED" -ForegroundColor Red
Write-Host ""

# Extract short SHA for readability
$apiShort = if ($apiImage -match "sha256:(.{12})") { $Matches[1] } else { $apiImage.Substring([Math]::Max(0, $apiImage.Length - 16)) }
$jobShort = if ($jobImage -match "sha256:(.{12})") { $Matches[1] } else { $jobImage.Substring([Math]::Max(0, $jobImage.Length - 16)) }

Write-Host "  API image: ...$apiShort"
Write-Host "  Job image: ...$jobShort"
Write-Host ""

if ($CheckOnly) {
    Write-Host "  Run without -CheckOnly to update the Job." -ForegroundColor Yellow
    Write-Host "  Command: .\sync-job-image.ps1" -ForegroundColor Gray
    exit 1
}

# Step 4: Update Job
Write-Host "[4/4] Updating Job to match API service..." -ForegroundColor Yellow
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
gcloud run jobs update $JobName --region $Region --image "$apiImage" 2>$null
$updateExitCode = $LASTEXITCODE
$ErrorActionPreference = $prevEAP
if ($updateExitCode -ne 0) {
    Write-Host "  ERROR: Failed to update Job '$JobName' (exit code $updateExitCode)" -ForegroundColor Red
    exit 1
}
Write-Host "  Job updated successfully." -ForegroundColor Green

# Verify
Write-Host ""
Write-Host "  Verifying..." -ForegroundColor Yellow
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$newJobImage = gcloud run jobs describe $JobName --region $Region --format 'value(spec.template.spec.template.spec.containers[0].image)' 2>$null
$ErrorActionPreference = $prevEAP
$newJobImage = $newJobImage.Trim()

if ($newJobImage -eq $apiImage) {
    Write-Host "  VERIFIED - Job now matches API service." -ForegroundColor Green
} else {
    Write-Host "  WARNING - Images still differ after update." -ForegroundColor Red
    Write-Host "  API: $apiImage"
    Write-Host "  Job: $newJobImage"
    exit 1
}

Write-Host ""
Write-Host "Done. Run 'gcloud run jobs execute $JobName --region $Region --wait' to test." -ForegroundColor Cyan
Write-Host ""
