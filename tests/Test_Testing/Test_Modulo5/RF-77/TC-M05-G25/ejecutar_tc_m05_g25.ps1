# | Fecha      | Nombre                   | Que se hizo                                                          |
# |------------|--------------------------|----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G25 RF-77: runner Pytest con staging de evidencias            |
<#
.SYNOPSIS
  Ejecuta TC-M05-G25 (RF-77, Roles, IDOR y Auditoria) contra TEST.

.DESCRIPTION
  - Carga .env.test del repo en las variables de entorno del PROCESO.
  - Verifica variables obligatorias para Producer, Vet, Admin y Sandbox.
  - Crea el staging evidencias\run-<yyyyMMdd-HHmmss>\ y define TEST_EVIDENCE_DIR.
  - Ejecuta pytest (-p no:randomly, --tb=short) con reporte HTML y JUnit XML.
  - Genera artefactos derivados (JSON, repro, MD, TXT).
  - Promocion condicionada: solo copia a resultados\ si 0 fallos y 0 secretos.
#>
param(
    [int]$Reintento = 0
)

$ErrorActionPreference = 'Stop'

# --- Rutas relativas
$tcDir       = $PSScriptRoot
$repo        = (Resolve-Path -LiteralPath (Join-Path $tcDir '..\..\..\..\..')).Path
$prueba      = Join-Path $tcDir 'test_tc_m05_g25.py'
$envFile     = Join-Path $repo '.env.test'
$rf77Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-77'
$rf76Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-76'

$g24Script   = Join-Path $rf77Dir 'TC-M05-G24\test_tc_m05_g24.py'
$g24Runner   = Join-Path $rf77Dir 'TC-M05-G24\ejecutar_tc_m05_g24.ps1'
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
$generadorPy = Join-Path $tcDir 'generar_artefactos_run_g25.py'

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
    if ($valor.Length -ge 2 -and (
            ($valor.StartsWith('"') -and $valor.EndsWith('"')) -or
            ($valor.StartsWith("'") -and $valor.EndsWith("'")))) {
        $valor = $valor.Substring(1, $valor.Length - 2)
    }
    [Environment]::SetEnvironmentVariable($nombre, $valor, 'Process')
}

# --- Verificacion de variables obligatorias
$obligatorias = @('TEST_BASE_URL', 'TEST_PRODUCER_EMAIL', 'TEST_PRODUCER_PASSWORD', 'TEST_ADMIN_EMAIL', 'TEST_ADMIN_PASSWORD', 'TEST_VET_EMAIL', 'TEST_VET_PASSWORD', 'TEST_SANDBOX_SECRET')
$faltan = 0
foreach ($n in $obligatorias) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($n, 'Process'))) {
        Write-Host "FALTA $n" -ForegroundColor Red
        $faltan++
    } else {
        Write-Host "OK $n"
    }
}
if ($faltan -gt 0) {
    Write-Host "Abortado: faltan $faltan variable(s) obligatoria(s)." -ForegroundColor Red
    exit 3
}

# --- Python
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source } else { $python = 'python' }
}

# --- SHA-256 iniciales
function Get-Sha256([string]$ruta) {
    if (-not (Test-Path -LiteralPath $ruta)) { return "NO_EXISTE" }
    return (Get-FileHash -LiteralPath $ruta -Algorithm SHA256).Hash.ToLowerInvariant()
}

$shaG25ScriptIni = Get-Sha256 $prueba
$shaG24ScriptIni = Get-Sha256 $g24Script
$shaG24RunnerIni = Get-Sha256 $g24Runner
$shaG19ScriptIni = Get-Sha256 $g19Script
$shaG19RunnerIni = Get-Sha256 $g19Runner
$shaG17ScriptIni = Get-Sha256 $g17Script
$shaG17RunnerIni = Get-Sha256 $g17Runner
$shaG16ScriptIni = Get-Sha256 $g16Script
$shaG16RunnerIni = Get-Sha256 $g16Runner
$shaG15ScriptIni = Get-Sha256 $g15Script
$shaG15RunnerIni = Get-Sha256 $g15Runner
$shaG14ScriptIni = Get-Sha256 $g14Script
$shaG14RunnerIni = Get-Sha256 $g14Runner

Write-Host "SHA-256 G25 Script inicio: $shaG25ScriptIni"
Write-Host "SHA-256 G24 Script inicio: $shaG24ScriptIni"
Write-Host "SHA-256 G19 Script inicio: $shaG19ScriptIni"
Write-Host "SHA-256 G17 Script inicio: $shaG17ScriptIni"
Write-Host "SHA-256 G16 Script inicio: $shaG16ScriptIni"
Write-Host "SHA-256 G15 Script inicio: $shaG15ScriptIni"
Write-Host "SHA-256 G14 Script inicio: $shaG14ScriptIni"

# --- Creacion del staging de evidencias
$marcaTiempo = Get-Date -Format 'yyyyMMdd-HHmmss'
$staging     = Join-Path $tcDir "evidencias\run-$marcaTiempo"
New-Item -ItemType Directory -Path $staging -Force | Out-Null

$htmlReport  = Join-Path $staging 'resultado_TC-M05-G25.html'
$xmlReport   = Join-Path $staging 'resultado_TC-M05-G25.xml'
$consoleLog  = Join-Path $staging 'consola_pytest.log'

# --- Variables de entorno del subproceso
[Environment]::SetEnvironmentVariable('TEST_EVIDENCE_DIR', $staging, 'Process')
[Environment]::SetEnvironmentVariable('PYTHONPATH', $repo, 'Process')
[Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'Process')

# --- Ejecucion de Pytest
$cronometro = [System.Diagnostics.Stopwatch]::StartNew()
Write-Host "Ejecutando suite TC-M05-G25 contra TEST..." -ForegroundColor Cyan

$salidaConsola = & $python -m pytest -p no:randomly --tb=short `
    --html=$htmlReport --self-contained-html `
    --junitxml=$xmlReport `
    $prueba 2>&1

$codigo = $LASTEXITCODE
$cronometro.Stop()
$duracionS = [Math]::Round($cronometro.Elapsed.TotalSeconds, 2)

# Guardar log de consola
$salidaConsola | Out-File -LiteralPath $consoleLog -Encoding utf8
$salidaConsola | ForEach-Object { Write-Host $_ }

# --- Generacion de artefactos derivados
if (Test-Path -LiteralPath $generadorPy) {
    Write-Host "Generando artefactos derivados en staging..."
    & $python $generadorPy --staging $staging --repo-root $repo --duracion-s $duracionS
}

# --- Verificacion de integridad SHA-256 post-corrida
$shaG25ScriptFin = Get-Sha256 $prueba
$shaG24ScriptFin = Get-Sha256 $g24Script
$shaG24RunnerFin = Get-Sha256 $g24Runner
$shaG19ScriptFin = Get-Sha256 $g19Script
$shaG19RunnerFin = Get-Sha256 $g19Runner
$shaG17ScriptFin = Get-Sha256 $g17Script
$shaG17RunnerFin = Get-Sha256 $g17Runner
$shaG16ScriptFin = Get-Sha256 $g16Script
$shaG16RunnerFin = Get-Sha256 $g16Runner
$shaG15ScriptFin = Get-Sha256 $g15Script
$shaG15RunnerFin = Get-Sha256 $g15Runner
$shaG14ScriptFin = Get-Sha256 $g14Script
$shaG14RunnerFin = Get-Sha256 $g14Runner

Write-Host "SHA-256 G25 Script fin:    $shaG25ScriptFin"
if ($shaG25ScriptIni -ne $shaG25ScriptFin) {
    Write-Host "ERROR CRITICO: El script de G25 fue modificado durante la ejecucion!" -ForegroundColor Red
    exit 5
}
if ($shaG24ScriptIni -ne $shaG24ScriptFin) {
    Write-Host "ERROR CRITICO: Los archivos de G24 fueron modificados!" -ForegroundColor Red
    exit 5
}
if ($shaG19ScriptIni -ne $shaG19ScriptFin -or $shaG19RunnerIni -ne $shaG19RunnerFin) {
    Write-Host "ERROR CRITICO: Los archivos de G19 fueron modificados!" -ForegroundColor Red
    exit 5
}
if ($shaG17ScriptIni -ne $shaG17ScriptFin -or $shaG17RunnerIni -ne $shaG17RunnerFin) {
    Write-Host "ERROR CRITICO: Los archivos de G17 fueron modificados!" -ForegroundColor Red
    exit 5
}
if ($shaG16ScriptIni -ne $shaG16ScriptFin -or $shaG16RunnerIni -ne $shaG16RunnerFin) {
    Write-Host "ERROR CRITICO: Los archivos de G16 fueron modificados!" -ForegroundColor Red
    exit 5
}
if ($shaG15ScriptIni -ne $shaG15ScriptFin -or $shaG15RunnerIni -ne $shaG15RunnerFin) {
    Write-Host "ERROR CRITICO: Los archivos de G15 fueron modificados!" -ForegroundColor Red
    exit 5
}
if ($shaG14ScriptIni -ne $shaG14ScriptFin -or $shaG14RunnerIni -ne $shaG14RunnerFin) {
    Write-Host "ERROR CRITICO: Los archivos de G14 fueron modificados!" -ForegroundColor Red
    exit 5
}
Write-Host "Integridad de suites previas G14-G24: 100% OK"

# --- Post-corrida de seguridad: escaneo de secretos
$claves = @(
    [Environment]::GetEnvironmentVariable('TEST_ADMIN_PASSWORD', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_PRODUCER_PASSWORD', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_VET_PASSWORD', 'Process')
)
$correos = @(
    [Environment]::GetEnvironmentVariable('TEST_ADMIN_EMAIL', 'Process'),
    [Environment]::GetEnvironmentVariable('TEST_PRODUCER_EMAIL', 'Process'),
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

# --- Promocion condicionada a resultados/
if ($codigo -eq 0 -and $quedan -eq 0) {
    Write-Host "Promoviendo reporte a resultados/ (0 fallos, 0 secretos, SHA-256 intacto)..." -ForegroundColor Green
    Copy-Item -LiteralPath (Join-Path $staging 'resultado_TC-M05-G25.html') -Destination (Join-Path $tcDir 'resultados\resultado_TC-M05-G25.html') -Force
    Copy-Item -LiteralPath (Join-Path $staging 'resultado_TC-M05-G25.json') -Destination (Join-Path $tcDir 'resultados\resultado_TC-M05-G25.json') -Force
    Write-Host "Promocion completada con exito en resultados/." -ForegroundColor Green
} else {
    Write-Host "No se promueve a resultados/ (codigo=$codigo, secretos=$quedan). Se conserva resultados/ limpio." -ForegroundColor Yellow
}
exit $codigo
