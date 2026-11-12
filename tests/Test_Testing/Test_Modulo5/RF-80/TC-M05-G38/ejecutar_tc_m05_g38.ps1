# | Fecha      | Nombre                   | Que se hizo                                                          |
# |------------|--------------------------|----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G38 RF-80: runner Pytest con staging de evidencias            |
<#
.SYNOPSIS
  Ejecuta TC-M05-G38 (RF-80, Consulta de Bitacora y Cadena de Custodia) contra TEST.

.DESCRIPTION
  - Carga .env.test del repo en las variables de entorno del PROCESO.
  - Verifica variables obligatorias para Admin, Vet y Sandbox.
  - Valida integridad de suites previas G14-G25 y G37.
  - Crea el staging evidencias\run-<yyyyMMdd-HHmmss>\ y define TEST_EVIDENCE_DIR.
  - Ejecuta pytest (-p no:randomly, --tb=short) con reporte HTML y JUnit XML.
  - Genera artefactos derivados (JSON, MD, TXT) via generar_artefactos_run_g38.py.
  - Escaneo estricto de secretos post-corrida.
  - Valida nuevamente integridad de suites previas.
#>
param(
    [int]$Reintento = 0
)

$ErrorActionPreference = 'Stop'

# --- Rutas relativas
$tcDir       = $PSScriptRoot
$repo        = (Resolve-Path -LiteralPath (Join-Path $tcDir '..\..\..\..\..')).Path
$prueba      = Join-Path $tcDir 'test_tc_m05_g38.py'
$envFile     = Join-Path $repo '.env.test'
$rf80Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-80'
$rf77Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-77'
$rf76Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-76'

$g37Script   = Join-Path $rf80Dir 'TC-M05-G37\test_tc_m05_g37.py'
$g37Runner   = Join-Path $rf80Dir 'TC-M05-G37\ejecutar_tc_m05_g37.ps1'
$g25Script   = Join-Path $rf77Dir 'TC-M05-G25\test_tc_m05_g25.py'
$g25Runner   = Join-Path $rf77Dir 'TC-M05-G25\ejecutar_tc_m05_g25.ps1'
$g24Script   = Join-Path $rf77Dir 'TC-M05-G24\test_tc_m05_g24.py'
$g24Runner   = Join-Path $rf77Dir 'TC-M05-G24\ejecutar_tc_m05_g24.ps1'
$g22Script   = Join-Path $rf77Dir 'TC-M05-G22\test_tc_m05_g22.py'
$g22Runner   = Join-Path $rf77Dir 'TC-M05-G22\ejecutar_tc_m05_g22.ps1'
$g21Script   = Join-Path $rf77Dir 'TC-M05-G21\test_tc_m05_g21.py'
$g21Runner   = Join-Path $rf77Dir 'TC-M05-G21\ejecutar_tc_m05_g21.ps1'
$g20Script   = Join-Path $rf77Dir 'TC-M05-G20\test_tc_m05_g20.py'
$g20Runner   = Join-Path $rf77Dir 'TC-M05-G20\ejecutar_tc_m05_g20.ps1'
$g19Script   = Join-Path $rf76Dir 'TC-M05-G19\test_tc_m05_g19.py'
$g19Runner   = Join-Path $rf76Dir 'TC-M05-G19\ejecutar_tc_m05_g19.ps1'
$g17Script   = Join-Path $rf76Dir 'TC-M05-G17\test_tc_m05_g17.py'
$g17Runner   = Join-Path $rf76Dir 'TC-M05-G17\ejecutar_tc_m05_g17.ps1'
$g16Script   = Join-Path $rf76Dir 'TC-M05-G16\test_tc_m05_g16.py'
$g16Runner   = Join-Path $rf76Dir 'TC-M05-G16\ejecutar_tc_m05_g16.ps1'
$g15Script   = Join-Path $rf76Dir 'TC-M05-G15\test_tc_m05_g15.py'
$g15Runner   = Join-Path $rf76Dir 'TC-M05-G15\ejecutar_tc_m05_g15.ps1'
$g14Script   = Join-Path $rf76Dir 'TC-M05-G14\test_tc_m05_g14.py'
$g14Runner   = Join-Path $rf76Dir 'TC-M05-G14\ejecutar_tc_m05_g14.ps1'
$generadorPy = Join-Path $tcDir 'generar_artefactos_run_g38.py'

if (-not (Test-Path -LiteralPath $prueba)) {
    Write-Host "FALTA el script de prueba: $prueba" -ForegroundColor Red
    exit 2
}
if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Host "FALTA .env.test en la raiz del repo ($repo)" -ForegroundColor Red
    exit 2
}

# --- Carga de .env.test en el proceso
foreach ($linea in Get-Content -LiteralPath $envFile -Encoding UTF8) {
    $t = $linea.Trim()
    if ($t -eq '' -or $t.StartsWith('#')) { continue }
    $i = $t.IndexOf('=')
    if ($i -lt 1) { continue }
    $nombre = $t.Substring(0, $i).Trim()
    $valor  = $t.Substring($i + 1).Trim()
    if ($valor.StartsWith('"') -and $valor.EndsWith('"') -and $valor.Length -ge 2) {
        $valor = $valor.Substring(1, $valor.Length - 2)
    } elseif ($valor.StartsWith("'") -and $valor.EndsWith("'") -and $valor.Length -ge 2) {
        $valor = $valor.Substring(1, $valor.Length - 2)
    }
    [Environment]::SetEnvironmentVariable($nombre, $valor, 'Process')
}

$variablesObligatorias = @(
    'TEST_BASE_URL',
    'TEST_SANDBOX_SECRET',
    'TEST_ADMIN_EMAIL',
    'TEST_ADMIN_PASSWORD',
    'TEST_VET_EMAIL',
    'TEST_VET_PASSWORD'
)
foreach ($v in $variablesObligatorias) {
    $val = [Environment]::GetEnvironmentVariable($v, 'Process')
    if ([string]::IsNullOrWhiteSpace($val)) {
        Write-Host "VARIABLE FALTANTE en .env.test: $v" -ForegroundColor Red
        exit 2
    }
}

# --- Snapshot inicial SHA-256 de suites previas
function Obtener-Sha256([string]$archivo) {
    if (-not (Test-Path -LiteralPath $archivo)) { return "NO_EXISTE" }
    return (Get-FileHash -LiteralPath $archivo -Algorithm SHA256).Hash.ToLowerInvariant()
}

$shaG37ScriptIni = Obtener-Sha256 $g37Script
$shaG37RunnerIni = Obtener-Sha256 $g37Runner
$shaG25ScriptIni = Obtener-Sha256 $g25Script
$shaG25RunnerIni = Obtener-Sha256 $g25Runner
$shaG24ScriptIni = Obtener-Sha256 $g24Script
$shaG24RunnerIni = Obtener-Sha256 $g24Runner
$shaG22ScriptIni = Obtener-Sha256 $g22Script
$shaG22RunnerIni = Obtener-Sha256 $g22Runner
$shaG21ScriptIni = Obtener-Sha256 $g21Script
$shaG21RunnerIni = Obtener-Sha256 $g21Runner
$shaG20ScriptIni = Obtener-Sha256 $g20Script
$shaG20RunnerIni = Obtener-Sha256 $g20Runner
$shaG19ScriptIni = Obtener-Sha256 $g19Script
$shaG19RunnerIni = Obtener-Sha256 $g19Runner
$shaG17ScriptIni = Obtener-Sha256 $g17Script
$shaG17RunnerIni = Obtener-Sha256 $g17Runner
$shaG16ScriptIni = Obtener-Sha256 $g16Script
$shaG16RunnerIni = Obtener-Sha256 $g16Runner
$shaG15ScriptIni = Obtener-Sha256 $g15Script
$shaG15RunnerIni = Obtener-Sha256 $g15Runner
$shaG14ScriptIni = Obtener-Sha256 $g14Script
$shaG14RunnerIni = Obtener-Sha256 $g14Runner

# --- Creacion del directorio de staging
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$runId     = "run-$timestamp"
$evidencias= Join-Path $tcDir 'evidencias'
$staging   = Join-Path $evidencias $runId

New-Item -ItemType Directory -Path $staging -Force | Out-Null

$htmlReport  = Join-Path $staging 'resultado_TC-M05-G38.html'
$xmlReport   = Join-Path $staging 'resultado_TC-M05-G38.xml'
$consolaLog  = Join-Path $staging 'console_execution.log'

# --- Variables de entorno del subproceso
[Environment]::SetEnvironmentVariable('TEST_EVIDENCE_DIR', $staging, 'Process')
[Environment]::SetEnvironmentVariable('PYTHONPATH', $repo, 'Process')
[Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'Process')

Write-Host "============================================================"
Write-Host "Ejecutando TC-M05-G38 (RF-80: Consulta de Bitacora y Custodia)"
Write-Host "Staging: $staging"
Write-Host "============================================================"

# --- Localizacion de python en venv
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'
$pythonCmd  = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }

$cronometro = [System.Diagnostics.Stopwatch]::StartNew()
$salidaConsola = & $pythonCmd -m pytest -p no:randomly --tb=short `
    --html=$htmlReport --self-contained-html `
    --junitxml=$xmlReport `
    -v $prueba 2>&1

$codigoPytest = $LASTEXITCODE
$cronometro.Stop()
$duracionS = [Math]::Round($cronometro.Elapsed.TotalSeconds, 2)

$salidaConsola | Out-File -LiteralPath $consolaLog -Encoding utf8
$salidaConsola | ForEach-Object { Write-Host $_ }

Write-Host "Pytest finalizo con codigo $codigoPytest en $duracionS s"

# --- Generacion de artefactos derivados
if (Test-Path -LiteralPath $generadorPy) {
    Write-Host "Generando artefactos derivados..."
    & $pythonCmd $generadorPy --staging $staging --repo-root $repo --duracion-s $duracionS
}

# --- Verificacion de integridad de suites previas
$shaG37ScriptFin = Obtener-Sha256 $g37Script
$shaG37RunnerFin = Obtener-Sha256 $g37Runner
$shaG25ScriptFin = Obtener-Sha256 $g25Script
$shaG25RunnerFin = Obtener-Sha256 $g25Runner
$shaG24ScriptFin = Obtener-Sha256 $g24Script
$shaG24RunnerFin = Obtener-Sha256 $g24Runner
$shaG22ScriptFin = Obtener-Sha256 $g22Script
$shaG22RunnerFin = Obtener-Sha256 $g22Runner
$shaG21ScriptFin = Obtener-Sha256 $g21Script
$shaG21RunnerFin = Obtener-Sha256 $g21Runner
$shaG20ScriptFin = Obtener-Sha256 $g20Script
$shaG20RunnerFin = Obtener-Sha256 $g20Runner
$shaG19ScriptFin = Obtener-Sha256 $g19Script
$shaG19RunnerFin = Obtener-Sha256 $g19Runner
$shaG17ScriptFin = Obtener-Sha256 $g17Script
$shaG17RunnerFin = Obtener-Sha256 $g17Runner
$shaG16ScriptFin = Obtener-Sha256 $g16Script
$shaG16RunnerFin = Obtener-Sha256 $g16Runner
$shaG15ScriptFin = Obtener-Sha256 $g15Script
$shaG15RunnerFin = Obtener-Sha256 $g15Runner
$shaG14ScriptFin = Obtener-Sha256 $g14Script
$shaG14RunnerFin = Obtener-Sha256 $g14Runner

if ($shaG37ScriptIni -ne $shaG37ScriptFin -or $shaG37RunnerIni -ne $shaG37RunnerFin -or
    $shaG25ScriptIni -ne $shaG25ScriptFin -or $shaG25RunnerIni -ne $shaG25RunnerFin -or
    $shaG24ScriptIni -ne $shaG24ScriptFin -or $shaG24RunnerIni -ne $shaG24RunnerFin -or
    $shaG22ScriptIni -ne $shaG22ScriptFin -or $shaG22RunnerIni -ne $shaG22RunnerFin -or
    $shaG21ScriptIni -ne $shaG21ScriptFin -or $shaG21RunnerIni -ne $shaG21RunnerFin -or
    $shaG20ScriptIni -ne $shaG20ScriptFin -or $shaG20RunnerIni -ne $shaG20RunnerFin -or
    $shaG19ScriptIni -ne $shaG19ScriptFin -or $shaG19RunnerIni -ne $shaG19RunnerFin -or
    $shaG17ScriptIni -ne $shaG17ScriptFin -or $shaG17RunnerIni -ne $shaG17RunnerFin -or
    $shaG16ScriptIni -ne $shaG16ScriptFin -or $shaG16RunnerIni -ne $shaG16RunnerFin -or
    $shaG15ScriptIni -ne $shaG15ScriptFin -or $shaG15RunnerIni -ne $shaG15RunnerFin -or
    $shaG14ScriptIni -ne $shaG14ScriptFin -or $shaG14RunnerIni -ne $shaG14RunnerFin) {
    Write-Host "ERROR CRITICO: Una suite previa fue modificada durante la ejecucion!" -ForegroundColor Red
    exit 5
}
Write-Host "Integridad de suites previas G14-G25 y G37: 100% OK"

# --- Escaneo y saneamiento de secretos
$claves = @(
    [Environment]::GetEnvironmentVariable('TEST_ADMIN_PASSWORD', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_VET_PASSWORD', 'Process')
)
$correos = @(
    [Environment]::GetEnvironmentVariable('TEST_ADMIN_EMAIL', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_VET_EMAIL', 'Process')
)
$secreto = [Environment]::GetEnvironmentVariable('TEST_SANDBOX_SECRET', 'Process')

$patrones = New-Object System.Collections.Generic.List[string]
foreach ($c in $claves) {
    if (-not [string]::IsNullOrEmpty($c)) {
        $patrones.Add($c)
        if ($c.Length -gt 20) { $patrones.Add($c.Substring($c.Length - 20)) }
    }
}
foreach ($e in $correos) {
    if (-not [string]::IsNullOrEmpty($e)) { $patrones.Add($e) }
}
if (-not [string]::IsNullOrEmpty($secreto)) {
    $patrones.Add($secreto)
    if ($secreto.Length -gt 20) { $patrones.Add($secreto.Substring($secreto.Length - 20)) }
}
$patrones.Add('eyJ')

$utf8 = New-Object System.Text.UTF8Encoding($false)
$artefactos = @(Get-ChildItem -LiteralPath $staging -File -Recurse)

function Contar-Secretos([string]$texto) {
    $n = 0
    foreach ($p in $patrones) { if ($texto.Contains($p)) { $n++ } }
    return $n
}

$quedan = 0
foreach ($a in $artefactos) {
    $texto = [IO.File]::ReadAllText($a.FullName, $utf8)
    if ((Contar-Secretos $texto) -gt 0) {
        foreach ($p in $patrones) { $texto = $texto.Replace($p, '***REDACTED***') }
        [IO.File]::WriteAllText($a.FullName, $texto, $utf8)
        Write-Host "Saneado: $($a.Name)" -ForegroundColor Yellow
        $revisado = [IO.File]::ReadAllText($a.FullName, $utf8)
        if ((Contar-Secretos $revisado) -gt 0) { $quedan++ }
    }
}
$claves = $null; $correos = $null; $secreto = $null; $patrones.Clear()

if ($quedan -gt 0) {
    Write-Host 'ARTEFACTOS CON SECRETOS: NO PROMOVER' -ForegroundColor Red
    exit 4
}
Write-Host 'Escaneo de secretos en staging: LIMPIO (0 secretos)'

exit $codigoPytest

