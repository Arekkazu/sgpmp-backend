<#
.SYNOPSIS
    Runner PowerShell para TC-M03-G179 (RF-63 Clasificación NIC41 vs TECNICO).
.DESCRIPTION
    Ejecuta la colección Newman de TC-M03-G179 bajo Sandbox transaccional con regla estricta de CERO DML.
    Genera el reporte oficial en resultados/resultado_TC-M03-G179.html.
#>
param (
    [string]$BaseUrl = "https://www.api.inmero.co/api-sgpmp-test"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Cargar variables de entorno desde .env.test si existen
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

$sandboxSecret = [System.Environment]::GetEnvironmentVariable("TEST_SANDBOX_SECRET")
$adminPassword = [System.Environment]::GetEnvironmentVariable("TEST_ADMIN_PASSWORD")

if (-not $sandboxSecret) {
    Write-Error "Variable TEST_SANDBOX_SECRET no definida en el entorno ni en .env.test"
}
if (-not $adminPassword) {
    Write-Error "Variable TEST_ADMIN_PASSWORD no definida en el entorno ni en .env.test"
}

# Verificación de CERO DML en la colección antes de correr
$collectionPath = Join-Path $scriptDir "test_tc_m03_g179.json"
$checkerScript = Join-Path $scriptDir "..\verificar_sin_dml.cjs"
if (Test-Path $checkerScript) {
    Write-Host "Verificando regla CERO DML en la colección..." -ForegroundColor Yellow
    node $checkerScript
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Chequeo CERO DML falló. Abortando ejecución."
    }
}

$runId = "test-g179-" + [System.Guid]::NewGuid().ToString().Substring(0, 8)
Write-Host "Iniciando ejecución de TC-M03-G179 con Run ID: $runId" -ForegroundColor Cyan

$resultadosDir = Join-Path $scriptDir "resultados"
if (-not (Test-Path $resultadosDir)) {
    New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null
}

$reportHtml = Join-Path $resultadosDir "resultado_TC-M03-G179_reintento1.html"
$reportXml  = Join-Path $resultadosDir "resultado_TC-M03-G179_reintento1.xml"
$reportJson = Join-Path $resultadosDir "resultado_TC-M03-G179_reintento1.json"

$newmanArgs = @(
    "run", $collectionPath,
    "--env-var", "baseUrl=$BaseUrl",
    "--env-var", "run_id=$runId",
    "--env-var", "sandbox_secret=$sandboxSecret",
    "--env-var", "admin_password=$adminPassword",
    "-r", "cli,htmlextra,junit",
    "--reporter-htmlextra-export", $reportHtml,
    "--reporter-htmlextra-title", "Reporte TC-M03-G179 - Clasificación NIC41 vs TECNICO Auditoría IoT (RF-63) - Reintento 1",
    "--reporter-htmlextra-omitRequestBodies",
    "--reporter-htmlextra-hideRequestBody", "00-Login-ADMIN",
    "--reporter-htmlextra-hideResponseBodies",
    "--reporter-junit-export", $reportXml
)

Write-Host "Ejecutando Newman..." -ForegroundColor Yellow
try {
    & npx -y newman @newmanArgs
} catch {
    Write-Warning "Newman completó con advertencias/fallos de aserción."
}

$generatorScript = Join-Path $scriptDir "generar_json_resultado.cjs"
if (Test-Path $generatorScript) {
    Write-Host "Generando JSON de checkpoints para el scanner..." -ForegroundColor Yellow
    node $generatorScript $reportXml $reportJson "TC-M03-G179"
}
Write-Host "Reportes generados en:" -ForegroundColor Green
Write-Host "  HTML: $reportHtml" -ForegroundColor Green
Write-Host "  XML:  $reportXml" -ForegroundColor Green
Write-Host "  JSON: $reportJson" -ForegroundColor Green
Write-Host "Para verificar en scanner (ejecutar en carpeta qa-dashboard/):" -ForegroundColor Cyan
Write-Host "cd ../../../qa-dashboard; python3 -c `"import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M03-G179'])`"" -ForegroundColor Green
