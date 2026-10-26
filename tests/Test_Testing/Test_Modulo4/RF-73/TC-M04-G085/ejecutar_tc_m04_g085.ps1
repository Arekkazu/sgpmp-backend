<#
.SYNOPSIS
    Runner PowerShell para TC-M04-G085 (RF-73 Retroalimentacion Clinica y Conflictos).
.DESCRIPTION
    Ejecuta la coleccion Newman de TC-M04-G085 bajo Sandbox transaccional con regla de CERO DML.
    Genera el reporte oficial en resultados/resultado_TC-M04-G085.html y .json.
#>
param (
    [string]$BaseUrl = "https://api.inmero.co/api-sgpmp-test",
    [string]$AdminPassword,
    [string]$Vet1Email,
    [string]$Vet1Password,
    [string]$Vet2Email,
    [string]$Vet2Password,
    [string]$SandboxSecret
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Cargar variables de entorno desde .env.test si existen
$envTestPath = Join-Path $scriptDir "..\..\..\..\..\.env.test"
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

# Resolucion de credenciales con fallback a variables de entorno sin hardcoding
if (-not $AdminPassword) {
    $AdminPassword = [System.Environment]::GetEnvironmentVariable("TEST_ADMIN_PASSWORD")
}
if (-not $AdminPassword) {
    Write-Error "ERROR: TEST_ADMIN_PASSWORD no definida en parametros, entorno ni .env.test"
    exit 2
}

if (-not $Vet1Email) {
    $Vet1Email = [System.Environment]::GetEnvironmentVariable("VET1_EMAIL")
    if (-not $Vet1Email) {
        $Vet1Email = "juan.carlos@email.com"
    }
}
if (-not $Vet1Password) {
    $Vet1Password = [System.Environment]::GetEnvironmentVariable("VET1_PASSWORD")
}
if (-not $Vet1Password) {
    Write-Error "ERROR: VET1_PASSWORD no definida en parametros, entorno ni .env.test"
    exit 2
}

if (-not $Vet2Email) {
    $Vet2Email = [System.Environment]::GetEnvironmentVariable("VET2_EMAIL")
    if (-not $Vet2Email) {
        $Vet2Email = "juanstesting@gmail.com"
    }
}
if (-not $Vet2Password) {
    $Vet2Password = [System.Environment]::GetEnvironmentVariable("VET2_PASSWORD")
}
if (-not $Vet2Password) {
    Write-Error "ERROR: VET2_PASSWORD no definida en parametros, entorno ni .env.test"
    exit 2
}

if (-not $SandboxSecret) {
    $SandboxSecret = [System.Environment]::GetEnvironmentVariable("TEST_SANDBOX_SECRET")
}
if (-not $SandboxSecret) {
    Write-Error "ERROR: TEST_SANDBOX_SECRET no definida en parametros, entorno ni .env.test"
    exit 2
}

# Verificacion de CERO DML en la coleccion antes de correr
$collectionPath = Join-Path $scriptDir "test_tc_m04_g085.json"
$checkerScript = Join-Path $scriptDir "..\verificar_sin_dml.cjs"
if (Test-Path $checkerScript) {
    Write-Host "Verificando regla CERO DML en la coleccion..." -ForegroundColor Yellow
    node $checkerScript
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Chequeo CERO DML fallo. Abortando ejecucion."
        exit 1
    }
}

$runId = "test-m04-g085-" + [System.Guid]::NewGuid().ToString().Substring(0, 8)
Write-Host "Iniciando ejecucion de TC-M04-G085 con Run ID: $runId" -ForegroundColor Cyan

# Carpeta resultados en minuscula (REGLA DE ORO #0)
$resultadosDir = Join-Path $scriptDir "resultados"
if (-not (Test-Path $resultadosDir)) {
    New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null
}

$reportHtml = Join-Path $resultadosDir "resultado_TC-M04-G085.html"
$reportRawJson = Join-Path $resultadosDir "_raw_newman.json"

$newmanArgs = @(
    "run", $collectionPath,
    "--env-var", "base_url=$BaseUrl",
    "--env-var", "baseUrl=$BaseUrl",
    "--env-var", "run_id=$runId",
    "--env-var", "admin_password=$AdminPassword",
    "--env-var", "vet1_email=$Vet1Email",
    "--env-var", "vet1_password=$Vet1Password",
    "--env-var", "vet2_email=$Vet2Email",
    "--env-var", "vet2_password=$Vet2Password",
    "--env-var", "sandbox_secret=$SandboxSecret",
    "-r", "cli,htmlextra,json",
    "--reporter-htmlextra-export", $reportHtml,
    "--reporter-htmlextra-title", "Reporte TC-M04-G085 - Retroalimentacion Clinica y Conflictos (RF-73)",
    "--reporter-htmlextra-hideRequestBody", "01-Login-Admin,02-Login-Vet1,03-Login-Vet2",
    "--reporter-json-export", $reportRawJson
)

Write-Host "Ejecutando Newman..." -ForegroundColor Yellow
$newmanExitCode = 0
try {
    & npx -y newman @newmanArgs
    $newmanExitCode = $LASTEXITCODE
} catch {
    Write-Warning "Newman completo con advertencias/fallos: $_"
    $newmanExitCode = 1
}

# Consolidar resultados en JSON
$consolidarScript = Join-Path $scriptDir "consolidar-resultados.cjs"
if (Test-Path $consolidarScript) {
    node $consolidarScript
}

# Post-proceso: asegurar schema oficial {tc, summary: {total, ok, falla, veredicto}, checkpoints}
$jsonReportPath = Join-Path $resultadosDir "resultado_TC-M04-G085.json"
if (Test-Path $jsonReportPath) {
    try {
        $rep = Get-Content $jsonReportPath -Raw | ConvertFrom-Json
        if (-not $rep.summary) {
            $total = if ($rep.stats) { $rep.stats.tests } else { 0 }
            $ok = if ($rep.stats) { $rep.stats.passes } else { 0 }
            $falla = if ($rep.stats) { $rep.stats.failures } else { 0 }
            $veredicto = if ($falla -eq 0 -and $total -gt 0) { "APROBADO" } else { "RECHAZADO" }
            $enriched = [ordered]@{
                tc = "TC-M04-G085"
                summary = [ordered]@{
                    total = $total
                    ok = $ok
                    falla = $falla
                    veredicto = $veredicto
                }
                checkpoints = $rep.checkpoints
            }
            $enriched | ConvertTo-Json -Depth 5 | Set-Content $jsonReportPath -Encoding ASCII
        }
    } catch {
        Write-Warning "No se pudo post-procesar schema de resultado: $_"
    }
}

Write-Host "Reporte HTML generado en: $reportHtml" -ForegroundColor Green
Write-Host "Para verificar en scanner (ejecutar en carpeta qa-dashboard/):" -ForegroundColor Cyan
Write-Host "cd ../../../qa-dashboard; python3 -c `"import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M04-G085'])`"" -ForegroundColor Green

$LASTEXITCODE = $newmanExitCode
exit $LASTEXITCODE
