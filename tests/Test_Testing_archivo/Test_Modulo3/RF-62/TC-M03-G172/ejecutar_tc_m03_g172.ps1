<#
.SYNOPSIS
    Runner PowerShell para TC-M03-G172 (RF-62) con k6.
.DESCRIPTION
    Ejecuta la suite k6 de rendimiento y capacidad para TC-M03-G172 bajo Sandbox transaccional.
    Genera el reporte JSON en resultados/resultado_TC-M03-G172.json para el scanner.
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

$runId = "test-g172-" + [System.Guid]::NewGuid().ToString().Substring(0, 8)
Write-Host "Iniciando ejecución de TC-M03-G172 con k6 bajo Run ID: $runId" -ForegroundColor Cyan

$resultadosDir = Join-Path $scriptDir "resultados"
if (-not (Test-Path $resultadosDir)) {
    New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null
}

$testScript = Join-Path $scriptDir "test_tc_m03_g172.js"
$summaryJson = Join-Path $resultadosDir "resultado_TC-M03-G172.json"

$env:baseUrl = $BaseUrl
$env:run_id = $runId
$env:sandbox_secret = $sandboxSecret
$env:admin_password = $adminPassword

Write-Host "Ejecutando k6..." -ForegroundColor Yellow
try {
    & k6 run --summary-export $summaryJson $testScript
} catch {
    Write-Warning "k6 completó con fallos de umbral o checks."
}

Write-Host "Reporte k6 generado en: $summaryJson" -ForegroundColor Green
Write-Host "Para verificar en scanner (ejecutar en carpeta qa-dashboard/):" -ForegroundColor Cyan
Write-Host "cd ../../../qa-dashboard; python3 -c `"import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M03-G172'])`"" -ForegroundColor Green
