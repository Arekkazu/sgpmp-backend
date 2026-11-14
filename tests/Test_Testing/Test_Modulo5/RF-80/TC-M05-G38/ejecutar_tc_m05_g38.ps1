# | Fecha      | Nombre                   | Que se hizo                                                                              |
# |------------|--------------------------|------------------------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G38 RF-80: runner Pytest con staging de evidencias                                |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G38 reevaluacion v2.0: sufijo _reintentoN, escaneo solo-reporte, ASCII puro       |
<#
.SYNOPSIS
  Ejecuta TC-M05-G38 (RF-80 v2.0, RFC-025) contra TEST.

.DESCRIPTION
  - Carga .env.test en variables de entorno del PROCESO.
  - Exige variables para Admin, Vet, Productor y Sandbox (Contador y Revisor Fiscal se validan dentro de pytest).
  - Verifica integridad SHA-256 de suites previas (G14-G25 y G37) y de resultados/.
  - Ejecuta pytest (-p no:randomly, --tb=short) con reporte HTML y JUnit XML con sufijo _reintentoN.
  - Invoca generar_artefactos_run_g38.py pasando --reintento.
  - Escanea secretos en staging en modo solo reporte (exit 4 si hay hallazgos, sin reescribir artefactos).
#>
param(
    [int]$Reintento = 0
)

$ErrorActionPreference = 'Stop'

# --- Rutas relativas
$tcDir       = $PSScriptRoot
$repo        = (Resolve-Path -LiteralPath (Join-Path $tcDir '..\..\..\..\..')).Path
$prueba      = Join-Path $tcDir 'test_tc_m05_g38.py'
$resultados  = Join-Path $tcDir 'resultados'
$envFile     = Join-Path $repo '.env.test'
$rf80Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-80'
$rf77Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-77'
$rf76Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-76'

$previos = @(
    (Join-Path $rf80Dir 'TC-M05-G37\test_tc_m05_g37.py'),
    (Join-Path $rf80Dir 'TC-M05-G37\ejecutar_tc_m05_g37.ps1'),
    (Join-Path $rf77Dir 'TC-M05-G25\test_tc_m05_g25.py'),
    (Join-Path $rf77Dir 'TC-M05-G25\ejecutar_tc_m05_g25.ps1'),
    (Join-Path $rf77Dir 'TC-M05-G24\test_tc_m05_g24.py'),
    (Join-Path $rf77Dir 'TC-M05-G24\ejecutar_tc_m05_g24.ps1'),
    (Join-Path $rf77Dir 'TC-M05-G22\test_tc_m05_g22.py'),
    (Join-Path $rf77Dir 'TC-M05-G22\ejecutar_tc_m05_g22.ps1'),
    (Join-Path $rf77Dir 'TC-M05-G21\test_tc_m05_g21.py'),
    (Join-Path $rf77Dir 'TC-M05-G21\ejecutar_tc_m05_g21.ps1'),
    (Join-Path $rf77Dir 'TC-M05-G20\test_tc_m05_g20.py'),
    (Join-Path $rf77Dir 'TC-M05-G20\ejecutar_tc_m05_g20.ps1'),
    (Join-Path $rf76Dir 'TC-M05-G19\test_tc_m05_g19.py'),
    (Join-Path $rf76Dir 'TC-M05-G19\ejecutar_tc_m05_g19.ps1'),
    (Join-Path $rf76Dir 'TC-M05-G17\test_tc_m05_g17.py'),
    (Join-Path $rf76Dir 'TC-M05-G17\ejecutar_tc_m05_g17.ps1'),
    (Join-Path $rf76Dir 'TC-M05-G16\test_tc_m05_g16.py'),
    (Join-Path $rf76Dir 'TC-M05-G16\ejecutar_tc_m05_g16.ps1'),
    (Join-Path $rf76Dir 'TC-M05-G15\test_tc_m05_g15.py'),
    (Join-Path $rf76Dir 'TC-M05-G15\ejecutar_tc_m05_g15.ps1'),
    (Join-Path $rf76Dir 'TC-M05-G14\test_tc_m05_g14.py'),
    (Join-Path $rf76Dir 'TC-M05-G14\ejecutar_tc_m05_g14.ps1')
)
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
    'TEST_PRODUCER_EMAIL',
    'TEST_PRODUCER_PASSWORD',
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

# --- Snapshot inicial SHA-256 de suites previas y de resultados/
function Obtener-Sha256([string]$archivo) {
    if (-not (Test-Path -LiteralPath $archivo)) { return 'NO_EXISTE' }
    return (Get-FileHash -LiteralPath $archivo -Algorithm SHA256).Hash.ToLowerInvariant()
}

$hashesPreviosIni = @{}
foreach ($p in $previos) {
    $hashesPreviosIni[$p] = Obtener-Sha256 $p
}

$hashesResIni = @{}
if (Test-Path -LiteralPath $resultados) {
    foreach ($f in Get-ChildItem -LiteralPath $resultados -File) {
        $hashesResIni[$f.FullName] = Obtener-Sha256 $f.FullName
    }
}

# --- Creacion del directorio de staging
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$runId     = "run-$timestamp"
$evidencias = Join-Path $tcDir 'evidencias'
$staging   = Join-Path $evidencias $runId

New-Item -ItemType Directory -Path $staging -Force | Out-Null

$sufijo      = if ($Reintento -gt 0) { "_reintento$Reintento" } else { '' }
$htmlReport  = Join-Path $staging "resultado_TC-M05-G38$sufijo.html"
$xmlReport   = Join-Path $staging "resultado_TC-M05-G38$sufijo.xml"
$consolaLog  = Join-Path $staging 'console_execution.log'

# --- Variables de entorno del subproceso
[Environment]::SetEnvironmentVariable('TEST_EVIDENCE_DIR', $staging, 'Process')
[Environment]::SetEnvironmentVariable('PYTHONPATH', $repo, 'Process')
[Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'Process')

Write-Host '============================================================'
Write-Host "Ejecutando TC-M05-G38 (RF-80 v2.0, RFC-025) [Reintento=$Reintento]"
Write-Host "Staging: $staging"
Write-Host '============================================================'

# --- Localizacion de python en venv
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'
$pythonCmd  = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }

$cronometro = [System.Diagnostics.Stopwatch]::StartNew()
$salidaConsola = & $pythonCmd -B -m pytest -p no:randomly --tb=short `
    --html=$htmlReport --self-contained-html `
    --junitxml=$xmlReport `
    -v $prueba 2>&1

$codigoPytest = $LASTEXITCODE
$cronometro.Stop()
$duracionS = [Math]::Round($cronometro.Elapsed.TotalSeconds, 2)

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines($consolaLog, @($salidaConsola | ForEach-Object { $_.ToString() }), $utf8NoBom)
$salidaConsola | ForEach-Object { Write-Host $_ }

Write-Host "Pytest finalizo con codigo $codigoPytest en $duracionS s"

# --- Generacion de artefactos derivados (NUNCA copia a resultados/)
if (Test-Path -LiteralPath $generadorPy) {
    Write-Host 'Generando artefactos derivados...'
    & $pythonCmd -B $generadorPy --staging $staging --repo-root $repo --duracion-s $duracionS --reintento $Reintento
}

# --- Verificacion de integridad de suites previas y resultados/
foreach ($p in $previos) {
    $fin = Obtener-Sha256 $p
    if ($hashesPreviosIni[$p] -ne $fin) {
        Write-Host "ERROR CRITICO: Suite previa modificada durante ejecucion: $p" -ForegroundColor Red
        exit 5
    }
}
Write-Host 'Integridad de suites previas G14-G25 y G37: 100% OK'

if (Test-Path -LiteralPath $resultados) {
    foreach ($f in Get-ChildItem -LiteralPath $resultados -File) {
        $finR = Obtener-Sha256 $f.FullName
        if (-not $hashesResIni.ContainsKey($f.FullName) -or $hashesResIni[$f.FullName] -ne $finR) {
            Write-Host "ERROR CRITICO: resultados/ fue alterado durante la corrida: $($f.Name)" -ForegroundColor Red
            exit 5
        }
    }
}
Write-Host 'Integridad de resultados/: intacta (sin promocion)'

# --- Escaneo de secretos SOLO REPORTE (nunca reescribe artefactos)
$claves = @(
    [Environment]::GetEnvironmentVariable('TEST_ADMIN_PASSWORD', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_PRODUCER_PASSWORD', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_VET_PASSWORD', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_ACCOUNTANT_PASSWORD', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_FISCAL_REVIEWER_PASSWORD', 'Process')
)
$correos = @(
    [Environment]::GetEnvironmentVariable('TEST_ADMIN_EMAIL', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_PRODUCER_EMAIL', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_VET_EMAIL', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_ACCOUNTANT_EMAIL', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_FISCAL_REVIEWER_EMAIL', 'Process')
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
$patrones.Add(('ey' + 'J'))

$artefactos = @(Get-ChildItem -LiteralPath $staging -File -Recurse)
$hallazgos = 0
foreach ($a in $artefactos) {
    $texto = [IO.File]::ReadAllText($a.FullName, $utf8NoBom)
    foreach ($p in $patrones) {
        if (-not [string]::IsNullOrEmpty($p) -and $texto.Contains($p)) {
            $hallazgos++
            Write-Host "SECRETO DETECTADO (no reescrito) en $($a.Name)" -ForegroundColor Red
            break
        }
    }
}
$claves = $null; $correos = $null; $secreto = $null; $patrones.Clear()

if ($hallazgos -gt 0) {
    Write-Host 'ARTEFACTOS CON SECRETOS: DETENER Y REPORTAR' -ForegroundColor Red
    exit 4
}
Write-Host 'Escaneo de secretos en staging: LIMPIO (0 hallazgos)'

exit $codigoPytest
