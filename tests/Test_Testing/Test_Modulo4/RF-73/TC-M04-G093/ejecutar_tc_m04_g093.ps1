<#
.SYNOPSIS
    Runner PowerShell para TC-M04-G093 (RF-73 Carga y Volumen con k6).
.DESCRIPTION
    Ejecuta el script k6 de TC-M04-G093 bajo Sandbox transaccional con regla de CERO DML.
    Genera el reporte oficial en resultados/resultado_TC-M04-G093.json con --summary-export.
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

$resultadosDir = Join-Path $scriptDir "resultados"
if (-not (Test-Path $resultadosDir)) {
    New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null
}

$k6Script = Join-Path $scriptDir "test_tc_m04_g093.js"
$summaryOut = Join-Path $resultadosDir "resultado_TC-M04-G093.json"

Write-Host "Ejecutando k6 para TC-M04-G093..." -ForegroundColor Yellow

$k6Args = @(
    "run",
    "-e", "BASE_URL=$BaseUrl",
    "-e", "TEST_SANDBOX_SECRET=$sandboxSecret",
    "-e", "TEST_ADMIN_PASSWORD=$adminPassword",
    "--summary-export=$summaryOut",
    $k6Script
)

try {
    & k6 @k6Args
} catch {
    Write-Warning "k6 completó con advertencias o códigos de salida no nulos."
}

Write-Host "Reporte k6 generado en: $summaryOut" -ForegroundColor Green
Write-Host "Para verificar en scanner (ejecutar en carpeta qa-dashboard/):" -ForegroundColor Cyan
Write-Host "cd ../../../qa-dashboard; python3 -c `"import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M04-G093'])`"" -ForegroundColor Green
exit $LASTEXITCODE
