<#
.SYNOPSIS
    Runner PowerShell para TC-M03-G178 (RF-63 Filtros de Auditoría IoT).
.DESCRIPTION
    Ejecuta la colección Newman de TC-M03-G178 bajo Sandbox transaccional con regla estricta de CERO DML.
    Genera el reporte oficial en resultados/resultado_TC-M03-G178.html.
#>
param (
    [string]$BaseUrl = "https://api.inmero.co/back-sigab-test"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Cargar variables de entorno desde .env.test si existen
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

$sandboxSecret = [System.Environment]::GetEnvironmentVariable("TEST_SANDBOX_SECRET")
$adminPassword = [System.Environment]::GetEnvironmentVariable("TEST_ADMIN_PASSWORD")

if (-not $sandboxSecret) {
    Write-Error "Variable TEST_SANDBOX_SECRET no definida en el entorno ni en .env.test"
}
if (-not $adminPassword) {
    Write-Error "Variable TEST_ADMIN_PASSWORD no definida en el entorno ni en .env.test"
}

# Verificación de CERO DML en la colección antes de correr
$collectionPath = Join-Path $scriptDir "test_tc_m03_g178.json"
$checkerScript = Join-Path $scriptDir "..\verificar_sin_dml.cjs"
if (Test-Path $checkerScript) {
    Write-Host "Verificando regla CERO DML en la colección..." -ForegroundColor Yellow
    node $checkerScript
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Chequeo CERO DML falló. Abortando ejecución."
    }
}

$runId = "test-g178-" + [System.Guid]::NewGuid().ToString().Substring(0, 8)
Write-Host "Iniciando ejecución de TC-M03-G178 con Run ID: $runId" -ForegroundColor Cyan

$resultadosDir = Join-Path $scriptDir "resultados"
if (-not (Test-Path $resultadosDir)) {
    New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null
}

$reportHtml = Join-Path $resultadosDir "resultado_TC-M03-G178.html"

$newmanArgs = @(
    "run", $collectionPath,
    "--env-var", "baseUrl=$BaseUrl",
    "--env-var", "run_id=$runId",
    "--env-var", "sandbox_secret=$sandboxSecret",
    "--env-var", "admin_password=$adminPassword",
    "-r", "cli,htmlextra",
    "--reporter-htmlextra-export", $reportHtml,
    "--reporter-htmlextra-title", "Reporte TC-M03-G178 - Filtros y Combinaciones Auditoría IoT (RF-63)",
    "--reporter-htmlextra-omitRequestBodies",
    "--reporter-htmlextra-hideRequestBody", "00-Login-ADMIN",
    "--reporter-htmlextra-hideResponseBodies"
)

Write-Host "Ejecutando Newman..." -ForegroundColor Yellow
try {
    & npx -y newman @newmanArgs
} catch {
    Write-Warning "Newman completó con advertencias/fallos de aserción."
}

Write-Host "Reporte generado en: $reportHtml" -ForegroundColor Green
Write-Host "Para verificar en scanner (ejecutar en carpeta qa-dashboard/):" -ForegroundColor Cyan
Write-Host "cd ../../../qa-dashboard; python3 -c `"import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M03-G178'])`"" -ForegroundColor Green
