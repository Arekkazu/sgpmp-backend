# | Fecha      | Nombre     | Que se hizo                                                 |
# |------------|------------|-------------------------------------------------------------|
# | 2026-10-30 | Juansegutt | TC-M03-G177 RF-63: correccion URL base, timeout, junit y reintento3 |
# | 2026-10-30 | Juansegutt | TC-M03-G177 RF-63: bloque try/finally garantizando teardown de seguridad |
# | 2026-10-30 | Juansegutt | TC-M03-G177 RF-63: correccion ruta a .env.test en raiz     |
<#
.SYNOPSIS
    Runner PowerShell para TC-M03-G177 (RF-63 Consulta Básica y Detalle de Auditoría IoT).
.DESCRIPTION
    Ejecuta la colección Newman de TC-M03-G177 bajo Sandbox transaccional con regla estricta de CERO DML.
    Genera los reportes oficiales en resultados/ (HTML, XML y JSON) para el scanner del dashboard.
    Asegura teardown preventivo mediante bloque try/finally.
#>
param (
    [string]$BaseUrl = $(if ($env:TEST_BASE_URL) { $env:TEST_BASE_URL } else { "https://api.inmero.co/api-sgpmp-test" })
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Cargar variables de entorno desde .env.test si existen (5 niveles a la raíz o fallback a 4)
$envTestPath = Join-Path $scriptDir "..\..\..\..\..\.env.test"
if (-not (Test-Path $envTestPath)) {
    $envTestPath = Join-Path $scriptDir "..\..\..\..\.env.test"
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
$collectionPath = Join-Path $scriptDir "test_tc_m03_g177.json"
$checkerScript = Join-Path $scriptDir "..\verificar_sin_dml.cjs"
if (Test-Path $checkerScript) {
    Write-Host "Verificando regla CERO DML en la colección..." -ForegroundColor Yellow
    node $checkerScript
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Chequeo CERO DML falló. Abortando ejecución."
    }
}

$runId = "test-g177-" + [System.Guid]::NewGuid().ToString().Substring(0, 8)
Write-Host "Iniciando ejecución de TC-M03-G177 con Run ID: $runId" -ForegroundColor Cyan

$resultadosDir = Join-Path $scriptDir "resultados"
if (-not (Test-Path $resultadosDir)) {
    New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null
}

$fechaHoy = Get-Date -Format "yyyyMMdd"
$evidenciasDir = Join-Path $scriptDir "evidencias\run-$fechaHoy"
if (-not (Test-Path $evidenciasDir)) {
    New-Item -ItemType Directory -Path $evidenciasDir -Force | Out-Null
}

$reportHtml = Join-Path $resultadosDir "resultado_TC-M03-G177_reintento3.html"
$reportXml  = Join-Path $resultadosDir "resultado_TC-M03-G177_reintento3.xml"
$reportJson = Join-Path $resultadosDir "resultado_TC-M03-G177_reintento3.json"
$consoleLog = Join-Path $evidenciasDir "console_execution.log"

$newmanArgs = @(
    "run", $collectionPath,
    "--env-var", "baseUrl=$BaseUrl",
    "--env-var", "run_id=$runId",
    "--env-var", "sandbox_secret=$sandboxSecret",
    "--env-var", "admin_password=$adminPassword",
    "--timeout-request", "15000",
    "-r", "cli,junit,htmlextra",
    "--reporter-junit-export", $reportXml,
    "--reporter-htmlextra-export", $reportHtml,
    "--reporter-htmlextra-title", "Reporte TC-M03-G177 Reintento 3 - Consulta Básica y Detalle Auditoría IoT (RF-63)",
    "--reporter-htmlextra-omitRequestBodies",
    "--reporter-htmlextra-hideRequestBody", "00-Login-ADMIN",
    "--reporter-htmlextra-hideResponseBodies"
)

try {
    Write-Host "Ejecutando Newman..." -ForegroundColor Yellow
    & npx -y newman @newmanArgs 2>&1 | Tee-Object -FilePath $consoleLog

    # Generar JSON estructurado para el scanner a partir del XML de JUnit
    $conversorScript = Join-Path $scriptDir "generar_json_resultado.cjs"
    if (Test-Path $conversorScript) {
        Write-Host "Generando JSON de checkpoints con generar_json_resultado.cjs..." -ForegroundColor Yellow
        node $conversorScript $reportXml $reportJson "TC-M03-G177"
    }

    Write-Host "Reportes generados:" -ForegroundColor Green
    Write-Host "  HTML: $reportHtml" -ForegroundColor Green
    Write-Host "  XML:  $reportXml" -ForegroundColor Green
    Write-Host "  JSON: $reportJson" -ForegroundColor Green
    Write-Host "  LOG:  $consoleLog" -ForegroundColor Green
} finally {
    # Teardown preventivo en caso de fallo prematuro de Newman antes del paso 99
    try {
        $checkUrl = "$BaseUrl/test-control/runs/$runId"
        $headers = @{ "X-Sandbox-Secret" = $sandboxSecret }
        $resp = Invoke-RestMethod -Uri $checkUrl -Method Delete -Headers $headers -ErrorAction SilentlyContinue
        if ($resp -and $resp.status) {
            Write-Host "Teardown de seguridad ejecutado en finally: $($resp.status)" -ForegroundColor Cyan
        }
    } catch {
        # Si ya fue revertido en el item 99, es normal que responda 404
    }
}

Write-Host "Para verificar en scanner (ejecutar en carpeta qa-dashboard/):" -ForegroundColor Cyan
Write-Host "cd ../../../qa-dashboard; python3 -c `"import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M03-G177'])`"" -ForegroundColor Green
