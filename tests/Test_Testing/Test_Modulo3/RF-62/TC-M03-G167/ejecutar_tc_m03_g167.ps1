param (
    [Alias("Sufijo")]
    [string]$Suffix = "_reintento2",
    [string]$BaseUrl = "https://www.api.inmero.co/api-sgpmp-test"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "../../../../..")).Path

# Cargar .env.test si existe (sin sobrescribir variables ya presentes en el proceso)
$envTestPath = Join-Path $repoRoot ".env.test"
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
    Write-Host "Exportalas en tu sesion de PowerShell antes de correr el script:" -ForegroundColor Yellow
    Write-Host '  $env:TEST_SANDBOX_SECRET = "..."' -ForegroundColor Yellow
    Write-Host '  $env:TEST_ADMIN_PASSWORD = "..."' -ForegroundColor Yellow
    Write-Host '  $env:BROKER_TOKEN = "..."'       -ForegroundColor Yellow
    exit 1
}

# Preparar carpetas
$resultadosDir = Join-Path $scriptDir "resultados"
$evidenciasDir = Join-Path $scriptDir "evidencias"
if (-not (Test-Path $resultadosDir)) { New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null }
if (-not (Test-Path $evidenciasDir)) { New-Item -ItemType Directory -Path $evidenciasDir -Force | Out-Null }

# Guardas de inmutabilidad: V1 y Reintentos no deben sobrescribirse
$V1Json = Join-Path $resultadosDir "resultado_TC-M03-G167.json"
$R1Json = Join-Path $resultadosDir "resultado_TC-M03-G167_reintento1.json"
$R2Json = Join-Path $resultadosDir "resultado_TC-M03-G167_reintento2.json"

if ([string]::IsNullOrEmpty($Suffix)) {
    Write-Error "Debe especificar -Suffix. Ejemplo: -Suffix '_reintento2'"
    exit 1
}

if (($Suffix -eq "_reintento1") -and (Test-Path $R1Json)) {
    Write-Error "Reintento 1 ya existe. Use un sufijo diferente (ej: _reintento2)."
    exit 1
}

if (($Suffix -eq "_reintento2") -and (Test-Path $R2Json)) {
    Write-Error "Reintento 2 ya existe. Use un sufijo diferente o archive el previo."
    exit 1
}

if (-not (Test-Path $V1Json)) {
    Write-Warning "V1 no encontrado."
}

$collectionPath = Join-Path $scriptDir "test_tc_m03_g167.json"
if (-not (Test-Path $collectionPath)) {
    Write-Host "ERROR: no se encontro $collectionPath" -ForegroundColor Red
    Write-Host "Ejecuta primero: node build_collection.cjs" -ForegroundColor Yellow
    exit 1
}

$reportHtml     = Join-Path $resultadosDir "resultado_TC-M03-G167$Suffix.html"
$reportJson     = Join-Path $resultadosDir "resultado_TC-M03-G167$Suffix.json"
$rawNewmanJson  = Join-Path $evidenciasDir "_raw_newman$Suffix.json"
$consoleLog     = Join-Path $evidenciasDir "console_run$Suffix.log"

# Generar run_id
$runId = "test-g167-" + [System.Guid]::NewGuid().ToString().Substring(0, 8)
Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " TC-M03-G167 - Deteccion de drift (RF-62 / RF-57 / RF-63) $Suffix" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Base URL : $BaseUrl"
Write-Host " run_id   : $runId"
Write-Host " Coleccion: test_tc_m03_g167.json"
Write-Host ""

# Construir args de Newman
$newmanArgs = @(
    "run", $collectionPath,
    "--timeout-request", "45000",
    "--env-var", "baseUrl=$BaseUrl",
    "--env-var", "run_id=$runId",
    "--env-var", "sandbox_secret=$sandboxSecret",
    "--env-var", "admin_password=$adminPassword",
    "--env-var", "broker_token=$brokerToken",
    "-r", "cli,htmlextra,json",
    "--reporter-htmlextra-export", $reportHtml,
    "--reporter-htmlextra-title", "TC-M03-G167 - Deteccion de drift (RF-62) $Suffix",
    "--reporter-htmlextra-omitRequestBodies",
    "--reporter-htmlextra-omitHeaders",
    "--reporter-htmlextra-hideRequestBody", "00.01-Login-Admin",
    "--reporter-htmlextra-hideResponseBodies",
    "--reporter-json-export", $rawNewmanJson
)

# Ejecutar Newman
$startTime = Get-Date
$newmanExit = 0
try {
    & npx -y newman @newmanArgs 2>&1 | Tee-Object -FilePath $consoleLog
    $newmanExit = $LASTEXITCODE
} catch {
    Write-Warning "Newman lanzo excepcion: $_"
    $newmanExit = 1
}
$elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 2)

# Consolidar JSON normativo
if (Test-Path $rawNewmanJson) {
    Write-Host "Consolidando resultados en $reportJson..." -ForegroundColor Cyan
    & node (Join-Path $scriptDir "consolidar-resultados.cjs") --input $rawNewmanJson --output $reportJson --suffix $Suffix
}

# Resumen
Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " RESUMEN" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host " run_id       : $runId"
Write-Host " Duracion     : $elapsed s"
Write-Host " Exit code    : $newmanExit"
Write-Host " Reporte HTML : $reportHtml"
Write-Host " Reporte JSON : $reportJson"
Write-Host " Consola      : $consoleLog"
Write-Host ""

if ($newmanExit -ne 0) {
    Write-Host " [AVISO] Newman reporto fallas de asercion (esperado si INC-M03-RF57 sigue vigente)." -ForegroundColor Yellow
    Write-Host "    Revisa el reporte HTML/JSON para el detalle de assertions fallidas." -ForegroundColor Yellow
}

if ($elapsed -gt 170) {
    Write-Host " [AVISO] Duracion cercana al timeout del sandbox (180s)." -ForegroundColor Yellow
}
