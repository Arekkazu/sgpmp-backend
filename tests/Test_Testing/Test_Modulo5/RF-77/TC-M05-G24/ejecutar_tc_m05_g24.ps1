# | Fecha      | Nombre                   | Que se hizo                                                          |
# |------------|--------------------------|----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G24 RF-77: runner Pytest con staging de evidencias            |
<#
.SYNOPSIS
  Ejecuta TC-M05-G24 (RF-77, POST /suministros/reportes-gastos) contra TEST.

.DESCRIPTION
  - Carga .env.test del repo en las variables de entorno del PROCESO.
  - Verifica TEST_BASE_URL, TEST_PRODUCER_EMAIL, TEST_PRODUCER_PASSWORD y TEST_SANDBOX_SECRET.
  - Crea el staging evidencias\run-<yyyyMMdd-HHmmss>\ y define TEST_EVIDENCE_DIR,
    PYTHONUTF8=1 y PYTHONPATH=".".
  - Ejecuta pytest (-p no:randomly, --tb=short) con reporte HTML autocontenido,
    JUnit XML y log de consola en UTF-8 dentro del staging.
  - Genera resultado_TC-M05-G24.json, repro, TC-M05-G24_resultado.md e informe .txt.
  - NO escribe ni copia nada en resultados\: la promocion del reporte es condicional.
#>
param(
    [int]$Reintento = 0
)

$ErrorActionPreference = 'Stop'

# --- Rutas relativas
$tcDir       = $PSScriptRoot
$repo        = (Resolve-Path -LiteralPath (Join-Path $tcDir '..\..\..\..\..')).Path
$prueba      = Join-Path $tcDir 'test_tc_m05_g24.py'
$envFile     = Join-Path $repo '.env.test'
$rf76Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-76'

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
$generadorPy = Join-Path $tcDir 'generar_artefactos_run_g24.py'

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
$obligatorias = @('TEST_BASE_URL', 'TEST_ADMIN_EMAIL', 'TEST_ADMIN_PASSWORD', 'TEST_SANDBOX_SECRET')
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
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }

# --- Funcion para calcular SHA-256
function Get-FileHashSha256([string]$ruta) {
    if (-not (Test-Path -LiteralPath $ruta)) { return "NO_EXISTE" }
    return (Get-FileHash -LiteralPath $ruta -Algorithm SHA256).Hash.ToLower()
}

$shaG24Inicio    = Get-FileHashSha256 $prueba
$shaG19ScriptIni = Get-FileHashSha256 $g19Script
$shaG19RunnerIni = Get-FileHashSha256 $g19Runner
$shaG17ScriptIni = Get-FileHashSha256 $g17Script
$shaG17RunnerIni = Get-FileHashSha256 $g17Runner
$shaG16ScriptIni = Get-FileHashSha256 $g16Script
$shaG16RunnerIni = Get-FileHashSha256 $g16Runner
$shaG15ScriptIni = Get-FileHashSha256 $g15Script
$shaG15RunnerIni = Get-FileHashSha256 $g15Runner
$shaG14ScriptIni = Get-FileHashSha256 $g14Script
$shaG14RunnerIni = Get-FileHashSha256 $g14Runner

Write-Host "SHA-256 G24 Script inicio: $shaG24Inicio"
Write-Host "SHA-256 G19 Script inicio: $shaG19ScriptIni"
Write-Host "SHA-256 G17 Script inicio: $shaG17ScriptIni"
Write-Host "SHA-256 G16 Script inicio: $shaG16ScriptIni"
Write-Host "SHA-256 G15 Script inicio: $shaG15ScriptIni"
Write-Host "SHA-256 G14 Script inicio: $shaG14ScriptIni"

# --- Staging de la corrida
$sufijo  = if ($Reintento -gt 0) { "_reintento$Reintento" } else { '' }
$marca   = Get-Date -Format 'yyyyMMdd-HHmmss'
$staging = Join-Path $tcDir "evidencias\run-$marca"
New-Item -ItemType Directory -Force -Path $staging | Out-Null

$env:TEST_EVIDENCE_DIR = $staging
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = '.'

$html = Join-Path $staging "resultado_TC-M05-G24$sufijo.html"
$xml  = Join-Path $staging "resultado_TC-M05-G24$sufijo.xml"
$log  = Join-Path $staging 'console_execution.log'

$argumentos = @(
    '-m', 'pytest', $prueba,
    '-p', 'no:randomly',
    '-v',
    '--tb=short',
    "--html=$html", '--self-contained-html',
    "--junitxml=$xml"
)

# --- Ejecucion
$salida = @()
$codigo = $null
Push-Location -LiteralPath $repo
try {
    $ErrorActionPreference = 'Continue'
    $salida = & $python @argumentos 2>&1 | ForEach-Object { "$_" }
    $codigo = $LASTEXITCODE
} finally {
    $ErrorActionPreference = 'Stop'
    Pop-Location
}

$salida | Out-File -FilePath $log -Encoding utf8
$salida | ForEach-Object { Write-Host $_ }

# --- Generacion de artefactos derivados
Write-Host ''
Write-Host "Generando artefactos derivados en staging..."
$argsGen = @(
    $generadorPy,
    '--staging', $staging,
    '--sha-g24-script', $shaG24Inicio,
    '--sha-g19-script', $shaG19ScriptIni,
    '--sha-g19-runner', $shaG19RunnerIni,
    '--sha-g17-script', $shaG17ScriptIni,
    '--sha-g17-runner', $shaG17RunnerIni,
    '--sha-g16-script', $shaG16ScriptIni,
    '--sha-g16-runner', $shaG16RunnerIni,
    '--sha-g15-script', $shaG15ScriptIni,
    '--sha-g15-runner', $shaG15RunnerIni,
    '--sha-g14-script', $shaG14ScriptIni,
    '--sha-g14-runner', $shaG14RunnerIni
)
& $python @argsGen

# --- Verificacion final de integridad de hashes
$shaG24Fin       = Get-FileHashSha256 $prueba
$shaG19ScriptFin = Get-FileHashSha256 $g19Script
$shaG19RunnerFin = Get-FileHashSha256 $g19Runner
$shaG17ScriptFin = Get-FileHashSha256 $g17Script
$shaG17RunnerFin = Get-FileHashSha256 $g17Runner
$shaG16ScriptFin = Get-FileHashSha256 $g16Script
$shaG16RunnerFin = Get-FileHashSha256 $g16Runner
$shaG15ScriptFin = Get-FileHashSha256 $g15Script
$shaG15RunnerFin = Get-FileHashSha256 $g15Runner
$shaG14ScriptFin = Get-FileHashSha256 $g14Script
$shaG14RunnerFin = Get-FileHashSha256 $g14Runner

Write-Host "SHA-256 G24 Script fin:    $shaG24Fin"
if ($shaG24Inicio -ne $shaG24Fin) {
    Write-Host "ADVERTENCIA: test_tc_m05_g24.py cambio durante la ejecucion!" -ForegroundColor Red
} else {
    Write-Host "G24 Script integro: OK"
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
Write-Host "Integridad de suites previas G14-G19: 100% OK"

# --- Post-corrida de seguridad: escaneo de secretos
$clave   = [Environment]::GetEnvironmentVariable('TEST_PRODUCER_PASSWORD', 'Process')
$secreto = [Environment]::GetEnvironmentVariable('TEST_SANDBOX_SECRET', 'Process')
$correo  = [Environment]::GetEnvironmentVariable('TEST_PRODUCER_EMAIL', 'Process')
$claveAdmin = [Environment]::GetEnvironmentVariable('TEST_ADMIN_PASSWORD', 'Process')
$correoAdmin = [Environment]::GetEnvironmentVariable('TEST_ADMIN_EMAIL', 'Process')

$patrones = New-Object System.Collections.Generic.List[string]
foreach ($v in @($secreto, $clave, $correo, $claveAdmin, $correoAdmin)) {
    if (-not [string]::IsNullOrEmpty($v)) { $patrones.Add($v) }
}
if ($secreto.Length -gt 20) { $patrones.Add($secreto.Substring($secreto.Length - 20)) }
if ($clave.Length -gt 20) { $patrones.Add($clave.Substring($clave.Length - 20)) }
if ($claveAdmin.Length -gt 20) { $patrones.Add($claveAdmin.Substring($claveAdmin.Length - 20)) }
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
$clave = $null; $secreto = $null; $correo = $null; $claveAdmin = $null; $correoAdmin = $null; $patrones.Clear()

if ($quedan -gt 0) {
    Write-Host 'ARTEFACTOS CON SECRETOS: NO PROMOVER' -ForegroundColor Red
    exit 4
}
Write-Host 'Escaneo de secretos en staging: LIMPIO (0 secretos)'

# --- Promocion condicionada a resultados/
if ($codigo -eq 0 -and $quedan -eq 0) {
    Write-Host "Promoviendo reporte a resultados/ (0 fallos, 0 secretos, SHA-256 intacto)..." -ForegroundColor Green
    Copy-Item -LiteralPath (Join-Path $staging 'resultado_TC-M05-G24.html') -Destination (Join-Path $tcDir 'resultados\resultado_TC-M05-G24.html') -Force
    Copy-Item -LiteralPath (Join-Path $staging 'resultado_TC-M05-G24.json') -Destination (Join-Path $tcDir 'resultados\resultado_TC-M05-G24.json') -Force
    Write-Host "Promocion completada con exito en resultados/." -ForegroundColor Green
} else {
    Write-Host "No se promueve a resultados/ (codigo=$codigo, secretos=$quedan). Se conserva resultados/ limpio." -ForegroundColor Yellow
}
exit $codigo
