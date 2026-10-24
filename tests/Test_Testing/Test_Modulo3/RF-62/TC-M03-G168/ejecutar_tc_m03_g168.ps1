<#
.SYNOPSIS
    Runner PowerShell para TC-M03-G168 (RF-62).
.DESCRIPTION
    Ejecuta la colección Newman de TC-M03-G168 bajo Sandbox transaccional, exportando
    el reporte oficial a resultados/resultado_TC-M03-G168.html (leído por el scanner).
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

# Generar run_id efímero
$runId = "test-g168-" + [System.Guid]::NewGuid().ToString().Substring(0, 8)
Write-Host "Iniciando ejecución de TC-M03-G168 con Run ID: $runId" -ForegroundColor Cyan

# Directorio de resultados computables para el scanner
$resultadosDir = Join-Path $scriptDir "resultados"
if (-not (Test-Path $resultadosDir)) {
    New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null
}

$collectionPath = Join-Path $scriptDir "test_tc_m03_g168.json"
$reportHtml = Join-Path $resultadosDir "resultado_TC-M03-G168.html"

# Ejecutar Newman con reporters cli y htmlextra
$newmanArgs = @(
    "run", $collectionPath,
    "--env-var", "baseUrl=$BaseUrl",
    "--env-var", "run_id=$runId",
    "--env-var", "sandbox_secret=$sandboxSecret",
    "--env-var", "admin_password=$adminPassword",
    "-r", "cli,htmlextra",
    "--reporter-htmlextra-export", $reportHtml,
    "--reporter-htmlextra-title", "Reporte TC-M03-G168 - Flags Individuales RF-62",
    "--reporter-htmlextra-omitRequestBodies",
    "--reporter-htmlextra-hideRequestBody", "00-Preflight-Login-Admin",
    "--reporter-htmlextra-hideResponseBodies"
)

Write-Host "Ejecutando Newman..." -ForegroundColor Yellow
try {
    & npx -y newman @newmanArgs
} catch {
    Write-Warning "Newman completó con fallos reportados en aserciones."
}

Write-Host "Reporte generado en: $reportHtml" -ForegroundColor Green
Write-Host "Para verificar en scanner:" -ForegroundColor Cyan
Write-Host "python3 -c `"import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M03-G168'])`"" -ForegroundColor Green
