<#
.SYNOPSIS
    Runner PowerShell para TC-M04-G083 (RF-73 Distribucion OTA e Integridad).
.DESCRIPTION
    Ejecuta la coleccion Newman de TC-M04-G083 bajo Sandbox transaccional con regla de CERO DML.
    Genera el reporte oficial en resultados/resultado_TC-M04-G083.html y .json.
#>
param (
    [string]$BaseUrl = "https://api.inmero.co/api-sgpmp-test",
    [string]$AdminPassword = "",
    [string]$BrokerToken = "",
    [string]$SandboxSecret = ""
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

# Resolver credenciales requeridas
if (-not $AdminPassword) {
    $AdminPassword = [System.Environment]::GetEnvironmentVariable("TEST_ADMIN_PASSWORD")
}
if (-not $AdminPassword) {
    Write-Error "ERROR: TEST_ADMIN_PASSWORD no definida en el entorno ni en .env.test"
    exit 2
}

if (-not $BrokerToken) {
    $BrokerToken = [System.Environment]::GetEnvironmentVariable("BROKER_SERVICE_TOKEN")
}
if (-not $BrokerToken) {
    Write-Error "ERROR: BROKER_SERVICE_TOKEN no definida en el entorno ni pasada por parametro -BrokerToken"
    exit 2
}

if (-not $SandboxSecret) {
    $SandboxSecret = [System.Environment]::GetEnvironmentVariable("TEST_SANDBOX_SECRET")
}
if (-not $SandboxSecret) {
    $SandboxSecret = "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff"
}

# Verificacion de CERO DML en la coleccion antes de correr
$collectionPath = Join-Path $scriptDir "test_tc_m04_g083.json"
$checkerScript = Join-Path $scriptDir "..\verificar_sin_dml.cjs"
if (Test-Path $checkerScript) {
    Write-Host "Verificando regla CERO DML en la coleccion..." -ForegroundColor Yellow
    node $checkerScript
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Chequeo CERO DML fallo. Abortando ejecucion."
        exit 1
    }
}

$runId = "test-m04-g083-" + [System.Guid]::NewGuid().ToString().Substring(0, 8)
Write-Host "Iniciando ejecucion de TC-M04-G083 con Run ID: $runId" -ForegroundColor Cyan

$resultadosDir = Join-Path $scriptDir "resultados"
if (-not (Test-Path $resultadosDir)) {
    New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null
}

$reportHtml = Join-Path $resultadosDir "resultado_TC-M04-G083.html"
$reportRawJson = Join-Path $resultadosDir "_raw_newman.json"

$newmanArgs = @(
    "run", $collectionPath,
    "--env-var", "base_url=$BaseUrl",
    "--env-var", "baseUrl=$BaseUrl",
    "--env-var", "run_id=$runId",
    "--env-var", "admin_password=$AdminPassword",
    "--env-var", "broker_token=$BrokerToken",
    "--env-var", "sandbox_secret=$SandboxSecret",
    "-r", "cli,htmlextra,json",
    "--reporter-htmlextra-export", $reportHtml,
    "--reporter-htmlextra-title", "Reporte TC-M04-G083 - Distribucion OTA e Integridad (RF-73)",
    "--reporter-htmlextra-hideRequestBody", "01-Login-ADMIN",
    "--reporter-json-export", $reportRawJson
)

Write-Host "Ejecutando Newman..." -ForegroundColor Yellow
$newmanExitCode = 0
try {
    & npx -y newman @newmanArgs
    $newmanExitCode = $LASTEXITCODE
} catch {
    Write-Warning "Newman completo con advertencias/fallos."
    $newmanExitCode = 1
}

# Consolidar resultados en JSON
$consolidarScript = Join-Path $scriptDir "consolidar-resultados.cjs"
if (Test-Path $consolidarScript) {
    node $consolidarScript
}

Write-Host "Reporte HTML generado en: $reportHtml" -ForegroundColor Green
Write-Host "Para verificar en scanner (ejecutar en carpeta qa-dashboard/):" -ForegroundColor Cyan
Write-Host "cd ../../../qa-dashboard; python3 -c `"import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M04-G083'])`"" -ForegroundColor Green

exit $newmanExitCode
