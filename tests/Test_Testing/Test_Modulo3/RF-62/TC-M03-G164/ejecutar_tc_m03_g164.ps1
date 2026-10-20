<#
.SYNOPSIS
    Script de ejecución automatizada con Newman para TC-M03-G164 (RF-62).
.DESCRIPTION
    Ejecuta la colección Postman/Newman validando variables de entorno,
    verificando ausencia de hardcodeos (L2 / M2 / M7 / M8), pasando credenciales y correos
    por --env-var, suprimiendo datos sensibles en el reporte htmlextra (L6)
    y escaneando fugas de seguridad posteriores.
#>

param(
    [string]$ModoDatos = "existentes", # opciones: existentes | sandbox | sql_dba
    [string]$BaseUrl = "https://api.inmero.co/back-sigab-test",
    [int]$StatusValidacionEsperado = 422
)

# M18: Cálculo dinámico de rutas basado en la ubicación del script ($PSScriptRoot)
$scriptDir = $PSScriptRoot
if (-not $scriptDir) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $scriptDir) {
    $scriptDir = (Get-Location).Path
}

$collectionPath = Join-Path $scriptDir "test_tc_m03_g164.json"
$verifierPath = Join-Path $scriptDir "verificar_hardcode_tc_m03_g164.cjs"
$resultadosDir = Join-Path $scriptDir "resultados"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando suite de pruebas: TC-M03-G164 (RF-62 - Calidad Telemetria)" -ForegroundColor Cyan
Write-Host "Directorio base: $scriptDir" -ForegroundColor Cyan
Write-Host "Modo de datos seleccionado: $ModoDatos" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Validar variables de entorno requeridas
$sandboxSecret = $env:TEST_SANDBOX_SECRET
$adminPassword = $env:TEST_ADMIN_PASSWORD
$productorPassword = $env:TEST_PRODUCER_PASSWORD
$ingenieroPassword = $env:TEST_FIELD_ENGINEER_PASSWORD

# M1 / M18: Correos configurables vía entorno con defaults
$adminEmail = if ($env:TEST_ADMIN_EMAIL) { $env:TEST_ADMIN_EMAIL } else { "administador.dev@gmail.com" }
$productorEmail = if ($env:TEST_PRODUCER_EMAIL) { $env:TEST_PRODUCER_EMAIL } else { "productor@pecuaria.co" }
$ingenieroEmail = if ($env:TEST_FIELD_ENGINEER_EMAIL) { $env:TEST_FIELD_ENGINEER_EMAIL } else { "ingeniero@pecuaria.co" }

if (-not $sandboxSecret) {
    Write-Error "ERROR: La variable de entorno TEST_SANDBOX_SECRET no esta definida."
    exit 1
}
if (-not $adminPassword) {
    Write-Error "ERROR: La variable de entorno TEST_ADMIN_PASSWORD no esta definida."
    exit 1
}
if (-not $productorPassword) {
    Write-Error "ERROR: La variable de entorno TEST_PRODUCER_PASSWORD no esta definida."
    exit 1
}
if (-not $ingenieroPassword) {
    Write-Error "ERROR: La variable de entorno TEST_FIELD_ENGINEER_PASSWORD no esta definida."
    exit 1
}

# 2. Chequeo estático previo contra hardcodeos (L2 / M2 / M7 / M8) con variables de entorno disponibles
Write-Host "`n[M8] Ejecutando verificacion estatica contra valores hardcodeados..." -ForegroundColor Cyan
node $verifierPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: La coleccion contiene valores hardcodeados o parametros no autorizados."
    exit 1
}

if (-not (Test-Path $resultadosDir)) {
    New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null
}

# 3. Calcular nombre de reporte incremental
$baseReportName = "resultado_TC-M03-G164"
$reportFile = Join-Path $resultadosDir "$baseReportName.html"
$reintento = 1
while (Test-Path $reportFile) {
    $reportFile = Join-Path $resultadosDir "${baseReportName}_reintento$reintento.html"
    $reintento++
}

Write-Host "Reporte destino: $reportFile" -ForegroundColor Yellow

# 4. Ejecución Newman con flags de seguridad htmlextra (L6) y variables completas (M1 / M18)
npx newman run $collectionPath `
  --env-var "baseUrl=$BaseUrl" `
  --env-var "sandbox_secret=$sandboxSecret" `
  --env-var "admin_email=$adminEmail" `
  --env-var "admin_password=$adminPassword" `
  --env-var "productor_email=$productorEmail" `
  --env-var "productor_password=$productorPassword" `
  --env-var "ingeniero_email=$ingenieroEmail" `
  --env-var "ingeniero_password=$ingenieroPassword" `
  --env-var "modo_datos=$ModoDatos" `
  --env-var "status_validacion_esperado=$StatusValidacionEsperado" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportFile `
  --reporter-htmlextra-title "Reporte TC-M03-G164 - Calidad Telemetria RF-62" `
  --reporter-htmlextra-skipHeaders "Authorization,X-Sandbox-Secret" `
  --reporter-htmlextra-hideRequestBody "NW-00-Setup-Login-Admin,NW-00-Setup-Login-Productor,NW-00-Setup-Login-Ingeniero" `
  --reporter-htmlextra-hideResponseBody "NW-00-Setup-Login-Admin,NW-00-Setup-Login-Productor,NW-00-Setup-Login-Ingeniero" `
  --reporter-htmlextra-skipEnvironmentVars "sandbox_secret,admin_password,productor_password,ingeniero_password"

$exitCode = $LASTEXITCODE

# 5. M18: Validar que el reporte HTML se haya generado; fallar si no existe
if (-not (Test-Path $reportFile)) {
    Write-Error "ERROR: El reporte HTML no fue generado en la ruta esperada: $reportFile"
    exit 1
}

# 6. Escaneo de seguridad sobre el HTML generado (L6)
Write-Host "`n[L6] Escaneando reporte HTML generado en busca de fugas de secretos y tokens..." -ForegroundColor Cyan
$htmlContent = Get-Content -Path $reportFile -Raw
$fugaDetectada = $false

if ($htmlContent.Contains($sandboxSecret)) {
    Write-Error "CRITICO: TEST_SANDBOX_SECRET expuesto en el reporte HTML."
    $fugaDetectada = $true
}
if ($htmlContent.Contains($adminPassword) -or $htmlContent.Contains($productorPassword) -or $htmlContent.Contains($ingenieroPassword)) {
    Write-Error "CRITICO: Contrasena de prueba expuesta en el reporte HTML."
    $fugaDetectada = $true
}
if ($htmlContent -match "eyJ[a-zA-Z0-9_-]{15,}\.eyJ[a-zA-Z0-9_-]{15,}") {
    Write-Error "CRITICO: Token JWT expuesto en el reporte HTML."
    $fugaDetectada = $true
}
if ($htmlContent -match "Bearer\s+(?!\{\{)[a-zA-Z0-9_\-\.]{15,}") {
    Write-Error "CRITICO: Patron 'Bearer <token>' literal expuesto en el reporte HTML."
    $fugaDetectada = $true
}

if ($fugaDetectada) {
    Remove-Item -Path $reportFile -Force
    Write-Error "El reporte HTML ha sido eliminado por motivos de seguridad debido a fuga de secretos."
    exit 1
} else {
    Write-Host "[L6 OK] Escaneo de seguridad limpio: cero credenciales, secretos, Bearer o tokens en el HTML." -ForegroundColor Green
}

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host "Ejecucion finalizada con codigo de salida: $exitCode" -ForegroundColor Cyan
Write-Host "Comando de verificacion pre-commit del scanner (QA Dashboard):" -ForegroundColor Green
Write-Host "python3 -c `"import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M03-G164'])`"" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Cyan

exit $exitCode
