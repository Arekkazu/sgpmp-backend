<#
.SYNOPSIS
    Runner PowerShell para TC-M03-G168 (Flags individuales de calidad).
.DESCRIPTION
    Ejecuta la colección Newman de TC-M03-G168 bajo Sandbox transaccional.
    Subcasos: TC-312 (outlier), TC-316 (gap), TC-317 (serie insuficiente), TC-323 (calibración).
.PARAMETER BaseUrl
    URL base de la API. Por defecto https://www.api.inmero.co/api-sgpmp-test.
.EXAMPLE
    .\ejecutar_tc_m03_g168.ps1
#>
[CmdletBinding()]
param (
    [string]$BaseUrl = "https://www.api.inmero.co/api-sgpmp-test"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Cargar .env.test si existe
$envTestPath = Join-Path $scriptDir "..\..\..\..\..\.env.test"
if (-not (Test-Path $envTestPath)) {
    $envTestPath = Join-Path $scriptDir "..\..\..\..\.env.test"
}
if (-not (Test-Path $envTestPath)) {
    $envTestPath = ".env.test"
}

if (Test-Path $envTestPath) {
    Get-Content $envTestPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $k = $parts[0].Trim()
            $v = $parts[1].Trim()
            if (-not [System.Environment]::GetEnvironmentVariable($k)) {
                [System.Environment]::SetEnvironmentVariable($k, $v, "Process")
            }
        }
    }
}

$sandboxSecret  = [System.Environment]::GetEnvironmentVariable("TEST_SANDBOX_SECRET")
$adminPassword  = [System.Environment]::GetEnvironmentVariable("TEST_ADMIN_PASSWORD")
$brokerToken    = [System.Environment]::GetEnvironmentVariable("BROKER_TOKEN")
if (-not $brokerToken) {
    $brokerToken = [System.Environment]::GetEnvironmentVariable("BROKER_SERVICE_TOKEN")
}

if (-not $sandboxSecret) {
    Write-Error "TEST_SANDBOX_SECRET no configurada. Abortando."
}
if (-not $adminPassword) {
    Write-Error "TEST_ADMIN_PASSWORD no configurada. Abortando."
}
if (-not $brokerToken) {
    Write-Error "BROKER_TOKEN (o BROKER_SERVICE_TOKEN) no configurada. Abortando."
}

$collectionPath = Join-Path $scriptDir "test_tc_m03_g168.json"
if (-not (Test-Path $collectionPath)) {
    Write-Error "Colección no encontrada: $collectionPath. Ejecutá 'node build_collection.cjs' primero."
}

$runId = "test-g168-" + [System.Guid]::NewGuid().ToString().Substring(0, 8)

$resultadosDir = Join-Path $scriptDir "resultados"
$evidenciasDir = Join-Path $scriptDir "evidencias"
if (-not (Test-Path $resultadosDir)) { New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null }
if (-not (Test-Path $evidenciasDir)) { New-Item -ItemType Directory -Path $evidenciasDir -Force | Out-Null }

$reportHtml = Join-Path $resultadosDir "resultado_TC-M03-G168_reintento1.html"
$reportJson = Join-Path $resultadosDir "resultado_TC-M03-G168_reintento1.json"
$runDir     = Join-Path $evidenciasDir "run-20261028"
if (-not (Test-Path $runDir)) { New-Item -ItemType Directory -Path $runDir -Force | Out-Null }
$consoleLog = Join-Path $runDir "console_execution.log"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "TC-M03-G168 - Flags individuales sin severidad (RF-62)" -ForegroundColor Cyan
Write-Host "BaseUrl:    $BaseUrl"
Write-Host "Run ID:     $runId"
Write-Host "Coleccion:  $collectionPath"
Write-Host "Reporte:    $reportHtml"
Write-Host "JSON:       $reportJson"
Write-Host "==========================================================" -ForegroundColor Cyan

$newmanArgs = @(
    "run", $collectionPath,
    "--env-var", "baseUrl=$BaseUrl",
    "--env-var", "run_id=$runId",
    "--env-var", "sandbox_secret=$sandboxSecret",
    "--env-var", "admin_password=$adminPassword",
    "--env-var", "broker_token=$brokerToken",
    "-r", "cli,htmlextra,json",
    "--reporter-htmlextra-export", $reportHtml,
    "--reporter-htmlextra-title", "TC-M03-G168 - Flags individuales sin severidad (Reintento 1)",
    "--reporter-htmlextra-omitRequestBodies",
    "--reporter-htmlextra-omitHeaders",
    "--reporter-json-export", $reportJson
)

$exitCode = 0
try {
    & newman @newmanArgs 2>&1 | Tee-Object -FilePath $consoleLog
    $exitCode = $LASTEXITCODE
} catch {
    Write-Warning "Fallo durante la ejecucion de Newman: $_"
    $exitCode = 1
} finally {
    Write-Host "`nVerificando cierre de sandbox..." -ForegroundColor Cyan
    try {
        $delUri = "$BaseUrl/test-control/runs/$runId"
        $delHeaders = @{ "X-Sandbox-Secret" = $sandboxSecret }
        $delResp = Invoke-RestMethod -Method DELETE -Uri $delUri -Headers $delHeaders -ErrorAction SilentlyContinue
        Write-Host "Sandbox cerrado via runner: $($delResp | ConvertTo-Json -Compress)" -ForegroundColor Green
    } catch {
        Write-Host "Sandbox ya habia sido cerrado por la coleccion." -ForegroundColor Gray
    }
}

exit $exitCode
