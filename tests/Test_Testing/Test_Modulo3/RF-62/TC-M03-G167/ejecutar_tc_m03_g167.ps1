<#
.SYNOPSIS
    Runner PowerShell para TC-M03-G167 (RF-62 / RF-57 / RF-63).
.DESCRIPTION
    Ejecuta la colección Newman de TC-M03-G167 bajo Sandbox transaccional.
    La colección es autosuficiente: crea finca/área/dispositivo/sensor en sandbox,
    calibra por escenario, ingesta 20 lecturas + 1 evaluada, evalúa calidad,
    verifica oráculo y hace rollback al final.

    Requiere en el entorno (o en .env.test):
      TEST_SANDBOX_SECRET   (obligatoria)
      TEST_ADMIN_PASSWORD   (obligatoria)
      BROKER_TOKEN          (obligatoria; alias: BROKER_SERVICE_TOKEN)
#>
param (
    [string]$BaseUrl = "https://www.api.inmero.co/api-sgpmp-test"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Cargar .env.test si existe (sin sobrescribir variables ya presentes en el proceso)
$envTestPath = Join-Path $scriptDir "..\..\..\..\.env.test"
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

# Resolver variables
$sandboxSecret  = [System.Environment]::GetEnvironmentVariable("TEST_SANDBOX_SECRET")
$adminPassword  = [System.Environment]::GetEnvironmentVariable("TEST_ADMIN_PASSWORD")
$brokerToken    = [System.Environment]::GetEnvironmentVariable("BROKER_TOKEN")
if (-not $brokerToken) {
    $brokerToken = [System.Environment]::GetEnvironmentVariable("BROKER_SERVICE_TOKEN")
}

$faltantes = @()
if (-not $sandboxSecret) { $faltantes += "TEST_SANDBOX_SECRET" }
if (-not $adminPassword) { $faltantes += "TEST_ADMIN_PASSWORD" }
if (-not $brokerToken)   { $faltantes += "BROKER_TOKEN (alias BROKER_SERVICE_TOKEN)" }
if ($faltantes.Count -gt 0) {
    Write-Host ""
    Write-Host "ERROR: faltan variables de entorno obligatorias:" -ForegroundColor Red
    $faltantes | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "Exportalas en tu sesión de PowerShell antes de correr el script:" -ForegroundColor Yellow
    Write-Host '  $env:TEST_SANDBOX_SECRET = "..."' -ForegroundColor Yellow
    Write-Host '  $env:TEST_ADMIN_PASSWORD = "..."' -ForegroundColor Yellow
    Write-Host '  $env:BROKER_TOKEN = "..."'       -ForegroundColor Yellow
    exit 1
}

# Generar run_id
$runId = "test-g167-" + [System.Guid]::NewGuid().ToString().Substring(0, 8)
Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " TC-M03-G167 — Detección de drift (RF-62 / RF-57 / RF-63)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Base URL : $BaseUrl"
Write-Host " run_id   : $runId"
Write-Host " Colección: test_tc_m03_g167.json"
Write-Host ""

# Preparar carpetas
$resultadosDir = Join-Path $scriptDir "resultados"
$evidenciasDir = Join-Path $scriptDir "evidencias"
if (-not (Test-Path $resultadosDir)) { New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null }
if (-not (Test-Path $evidenciasDir)) { New-Item -ItemType Directory -Path $evidenciasDir -Force | Out-Null }

$collectionPath = Join-Path $scriptDir "test_tc_m03_g167.json"
$sufijo = ""
if (Test-Path "$resultadosDir/resultado_TC-M03-G167_reintento1.json") {
    $n = 1
    while (Test-Path "$resultadosDir/resultado_TC-M03-G167_reintento$($n+1).json") { $n++ }
    $sufijo = "_reintento$($n+1)"
} elseif (Test-Path "$resultadosDir/resultado_TC-M03-G167.json") {
    $sufijo = "_reintento1"
}

    $reportHtml     = Join-Path $resultadosDir "resultado_TC-M03-G167$sufijo.html"
    $consoleLog     = Join-Path $evidenciasDir "console_run$sufijo.log"

if (-not (Test-Path $collectionPath)) {
    Write-Host "ERROR: no se encontró $collectionPath" -ForegroundColor Red
    Write-Host "Ejecutá primero: node build_collection.cjs" -ForegroundColor Yellow
    exit 1
}

# Construir args de Newman
$newmanArgs = @(
    "run", $collectionPath,
    "--timeout-request", "45000",
    "--env-var", "baseUrl=$BaseUrl",
    "--env-var", "run_id=$runId",
    "--env-var", "sandbox_secret=$sandboxSecret",
    "--env-var", "admin_password=$adminPassword",
    "--env-var", "broker_token=$brokerToken",
    "-r", "cli,htmlextra",
    "--reporter-htmlextra-export", $reportHtml,
    "--reporter-htmlextra-title", "TC-M03-G167 - Deteccion de drift (RF-62) $sufijo",
    "--reporter-htmlextra-omitRequestBodies",
    "--reporter-htmlextra-omitHeaders",
    "--reporter-htmlextra-hideRequestBody", "00.01-Login-Admin",
    "--reporter-htmlextra-hideResponseBodies"
)

# Ejecutar Newman
$startTime = Get-Date
$newmanExit = 0
try {
    & npx -y newman @newmanArgs 2>&1 | Tee-Object -FilePath $consoleLog
    $newmanExit = $LASTEXITCODE
} catch {
    Write-Warning "Newman lanzó excepción: $_"
    $newmanExit = 1
}
$elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 2)

# Resumen
Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " RESUMEN" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host " run_id       : $runId"
Write-Host " Duración     : $elapsed s"
Write-Host " Exit code    : $newmanExit"
Write-Host " Reporte HTML : $reportHtml"
Write-Host " Consola      : $consoleLog"
Write-Host ""

if ($newmanExit -ne 0) {
    Write-Host " ⚠️  Newman reportó fallas de aserción (esperado si INC-M03-RF57 sigue vigente)." -ForegroundColor Yellow
    Write-Host "    Revisá el reporte HTML para el detalle de assertions fallidas." -ForegroundColor Yellow
}

if ($elapsed -gt 170) {
    Write-Host " ⚠️  Duración cercana al timeout del sandbox (180s)." -ForegroundColor Yellow
}
