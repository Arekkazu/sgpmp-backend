# | Fecha      | Nombre                   | Que se hizo                                                 |
# |------------|--------------------------|-------------------------------------------------------------|
# | 2026-10-30 | Juan Sebastian Gutierrez | TC-M03-G191 RF-63: creacion de runner Pytest con reporteria |
# | 2026-11-01 | Juan Sebastian Gutierrez | TC-M03-G191 RF-63: parametrizar Suffix y proteccion V1/R1   |
<#
.SYNOPSIS
    Runner PowerShell para TC-M03-G191 (RF-63 CA-13 Tolerancia a eventos incompletos en Auditoría IoT).
.DESCRIPTION
    Ejecuta la suite Pytest de TC-M03-G191 bajo base de datos TEST con rollback transaccional automático.
    Genera los reportes oficiales en resultados/ (HTML, XML y JSON) y evidencias/run-YYYYMMDD/.
    Propaga el código de salida de Pytest de manera fidedigna.
#>
param(
    [string]$Suffix = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Localizar repo root buscando .env.test hacia arriba
$repoRoot = $scriptDir
while ($repoRoot -and -not (Test-Path (Join-Path $repoRoot ".env.test")) -and (Split-Path $repoRoot -Parent) -ne $repoRoot) {
    $repoRoot = Split-Path $repoRoot -Parent
}
if (-not (Test-Path (Join-Path $repoRoot ".env.test"))) {
    $repoRoot = (Get-Item (Join-Path $scriptDir "..\..\..\..\..")).FullName
}

# 2. Cargar variables de entorno desde .env.test
$envTestPath = Join-Path $repoRoot ".env.test"
if (Test-Path $envTestPath) {
    Get-Content $envTestPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $k = $parts[0].Trim()
            $v = $parts[1].Trim().Trim('"').Trim("'")
            if (-not [System.Environment]::GetEnvironmentVariable($k)) {
                [System.Environment]::SetEnvironmentVariable($k, $v, "Process")
            }
        }
    }
}

# 3. Exportar variables requeridas por pytest y conftest.py
$testDbUrl = [System.Environment]::GetEnvironmentVariable("TEST_DATABASE_URL")
if (-not $testDbUrl) {
    Write-Error "Variable TEST_DATABASE_URL no definida en el entorno ni en .env.test"
}

# Validar que TEST_DATABASE_URL apunte a PostgreSQL TEST
if (-not $testDbUrl.StartsWith("postgresql://")) {
    Write-Error "TEST_DATABASE_URL no es PostgreSQL: $testDbUrl"
}
if ($testDbUrl -like "*localhost*" -or $testDbUrl -like "*127.0.0.1*" -or $testDbUrl -like "*sqlite*") {
    Write-Error "TEST_DATABASE_URL apunta a entorno local/sqlite, se requiere PostgreSQL TEST"
}
if ($testDbUrl -notlike "*test*") {
    Write-Warning "TEST_DATABASE_URL no contiene la palabra 'test' en su cadena de conexión"
}

# Asegurar PYTHONPATH en la raíz del backend
$env:PYTHONPATH = $repoRoot

# 4. Resolver ejecutable de Python
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonCmd = Get-Command "python" -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $pythonExe = "python"
    } else {
        Write-Error "No se encontró python en .venv ni en PATH"
    }
}

# 5. Configurar rutas de resultados y evidencias
$resultadosDir = Join-Path $scriptDir "resultados"
if (-not (Test-Path $resultadosDir)) {
    New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null
}

$V1Json = Join-Path $resultadosDir "resultado_TC-M03-G191.json"
$R1Json = Join-Path $resultadosDir "resultado_TC-M03-G191_reintento1.json"
if ([string]::IsNullOrEmpty($Suffix) -and (Test-Path $V1Json) -and (Test-Path $R1Json)) {
    Write-Error "V1 y Reintento 1 ya existen. Use -Suffix '_reintentoN' para no sobrescribir."
    exit 1
}

$fechaHoy = Get-Date -Format "yyyyMMdd"
$evidenciasDir = Join-Path $scriptDir "evidencias\run-$fechaHoy"
if (-not (Test-Path $evidenciasDir)) {
    New-Item -ItemType Directory -Path $evidenciasDir -Force | Out-Null
}

$reportXml  = Join-Path $resultadosDir "resultado_TC-M03-G191$Suffix.xml"
$reportHtml = Join-Path $resultadosDir "resultado_TC-M03-G191$Suffix.html"
$reportJson = Join-Path $resultadosDir "resultado_TC-M03-G191$Suffix.json"
$consoleLog = Join-Path $evidenciasDir "console_execution.log"

$testFile = Join-Path $scriptDir "test_tc_m03_g191.py"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Iniciando ejecución Pytest: TC-M03-G191 (RF-63 CA-13)" -ForegroundColor Cyan
Write-Host "BD Destino: $testDbUrl" -ForegroundColor Gray
Write-Host "Archivo test: $testFile" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan

# 6. Ejecutar Pytest
$codePytest = 0
try {
    $pytestArgs = @(
        "-m", "pytest",
        $testFile,
        "-v",
        "--junitxml=$reportXml",
        "--html=$reportHtml",
        "--self-contained-html",
        "--tb=short"
    )
    & $pythonExe @pytestArgs 2>&1 | Tee-Object -FilePath $consoleLog
    $codePytest = $LASTEXITCODE
} catch {
    Write-Warning "Pytest finalizó con error de ejecución: $_"
    $codePytest = 1
}

# 7. Convertir XML a JSON para el scanner del dashboard
$conversorScript = Join-Path $scriptDir "generar_json_resultado.cjs"
if (Test-Path $conversorScript) {
    if (Test-Path $reportXml) {
        Write-Host "Generando JSON estructurado para el scanner..." -ForegroundColor Yellow
        try {
            & node $conversorScript $reportXml $reportJson "TC-M03-G191"
        } catch {
            Write-Warning "No se pudo ejecutar generar_json_resultado.cjs: $_"
        }
    } else {
        Write-Warning "No se encontró el XML de JUnit en $reportXml"
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Ejecución finalizada con exit code: $codePytest" -ForegroundColor Cyan
Write-Host "Reportes:" -ForegroundColor Gray
Write-Host "  HTML: $reportHtml" -ForegroundColor Gray
Write-Host "  XML:  $reportXml" -ForegroundColor Gray
Write-Host "  JSON: $reportJson" -ForegroundColor Gray
Write-Host "  LOG:  $consoleLog" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan

# 8. Propagar honestamente el código de salida de Pytest
exit $codePytest

