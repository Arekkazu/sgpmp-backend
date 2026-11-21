# | Fecha      | Nombre                   | Que se hizo                                                          |
# |------------|--------------------------|----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G17 RF-76: runner Pytest con staging y promoción condicionada |
<#
.SYNOPSIS
  Ejecuta TC-M05-G17 (RF-76, POST /suministros/medicamentos) contra API Real de TEST sobre activo QA desechable.

.DESCRIPTION
  - Carga .env.test del repo en las variables de entorno del PROCESO (sin imprimir valores).
  - Verifica variables obligatorias.
  - Comprueba integridad SHA-256 de G14, G15, G16, G19 al inicio y al final.
  - Crea el staging evidencias\run-<yyyyMMdd-HHmmss>\ y define TEST_EVIDENCE_DIR,
    PYTHONUTF8=1 y PYTHONPATH=".".
  - Ejecuta pytest (orden de archivo, -p no:randomly) con reporte HTML autocontenido,
    JUnit XML y log de consola en UTF-8, todo dentro del staging.
  - Invoca generar_artefactos_run_g17.py para generar JSON, repro, Markdown e Informe TXT.
  - Escaneo de secretos riguroso en staging (4 cuentas + sandbox, últimos 20 caracteres, eyJ).
  - Promoción condicionada a resultados/ si la corrida es 100% aprobada y limpia.
#>
param(
    [int]$Reintento = 0
)

$ErrorActionPreference = 'Stop'

# --- Rutas relativas
$tcDir       = $PSScriptRoot
$repo        = (Resolve-Path -LiteralPath (Join-Path $tcDir '..\..\..\..\..')).Path
$prueba      = Join-Path $tcDir 'test_tc_m05_g17.py'
$envFile     = Join-Path $repo '.env.test'
$g16Dir      = Join-Path $tcDir '..\TC-M05-G16'
$g16Script   = Join-Path $g16Dir 'test_tc_m05_g16.py'
$g16Runner   = Join-Path $g16Dir 'ejecutar_tc_m05_g16.ps1'
$g15Dir      = Join-Path $tcDir '..\TC-M05-G15'
$g15Script   = Join-Path $g15Dir 'test_tc_m05_g15.py'
$g15Runner   = Join-Path $g15Dir 'ejecutar_tc_m05_g15.ps1'
$g14Dir      = Join-Path $tcDir '..\TC-M05-G14'
$g14Script   = Join-Path $g14Dir 'test_tc_m05_g14.py'
$g14Runner   = Join-Path $g14Dir 'ejecutar_tc_m05_g14.ps1'
$g19Dir      = Join-Path $tcDir '..\TC-M05-G19'
$g19Script   = Join-Path $g19Dir 'test_tc_m05_g19.py'
$g19Runner   = Join-Path $g19Dir 'ejecutar_tc_m05_g19.ps1'
$generadorPy = Join-Path $tcDir 'generar_artefactos_run_g17.py'
$resultadosDir = Join-Path $tcDir 'resultados'

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
$obligatorias = @('TEST_BASE_URL', 'TEST_ADMIN_EMAIL', 'TEST_ADMIN_PASSWORD')
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

$shaG17Inicio    = Get-FileHashSha256 $prueba
$shaG16ScriptIni = Get-FileHashSha256 $g16Script
$shaG16RunnerIni = Get-FileHashSha256 $g16Runner
$shaG15ScriptIni = Get-FileHashSha256 $g15Script
$shaG15RunnerIni = Get-FileHashSha256 $g15Runner
$shaG14ScriptIni = Get-FileHashSha256 $g14Script
$shaG14RunnerIni = Get-FileHashSha256 $g14Runner
$shaG19ScriptIni = Get-FileHashSha256 $g19Script
$shaG19RunnerIni = Get-FileHashSha256 $g19Runner

Write-Host "SHA-256 G17 Script inicio: $shaG17Inicio"
Write-Host "SHA-256 G16 Script inicio: $shaG16ScriptIni"
Write-Host "SHA-256 G16 Runner inicio: $shaG16RunnerIni"
Write-Host "SHA-256 G15 Script inicio: $shaG15ScriptIni"
Write-Host "SHA-256 G15 Runner inicio: $shaG15RunnerIni"
Write-Host "SHA-256 G14 Script inicio: $shaG14ScriptIni"
Write-Host "SHA-256 G14 Runner inicio: $shaG14RunnerIni"
Write-Host "SHA-256 G19 Script inicio: $shaG19ScriptIni"
Write-Host "SHA-256 G19 Runner inicio: $shaG19RunnerIni"

# --- Staging de la corrida
$sufijo  = if ($Reintento -gt 0) { "_reintento$Reintento" } else { '' }
$marca   = Get-Date -Format 'yyyyMMdd-HHmmss'
$staging = Join-Path $tcDir "evidencias\run-$marca"
New-Item -ItemType Directory -Force -Path $staging | Out-Null

$env:TEST_EVIDENCE_DIR = $staging
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = '.'

$html = Join-Path $staging "resultado_TC-M05-G17$sufijo.html"
$xml  = Join-Path $staging "resultado_TC-M05-G17$sufijo.xml"
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
    '--sha-g17-inicio', $shaG17Inicio,
    '--sha-g16-script', $shaG16ScriptIni,
    '--sha-g16-runner', $shaG16RunnerIni,
    '--sha-g15-script', $shaG15ScriptIni,
    '--sha-g15-runner', $shaG15RunnerIni,
    '--sha-g14-script', $shaG14ScriptIni,
    '--sha-g14-runner', $shaG14RunnerIni,
    '--sha-g19-script', $shaG19ScriptIni,
    '--sha-g19-runner', $shaG19RunnerIni
)
& $python @argsGen

# --- Verificacion final de integridad de hashes
$shaG17Fin       = Get-FileHashSha256 $prueba
$shaG16ScriptFin = Get-FileHashSha256 $g16Script
$shaG16RunnerFin = Get-FileHashSha256 $g16Runner
$shaG15ScriptFin = Get-FileHashSha256 $g15Script
$shaG15RunnerFin = Get-FileHashSha256 $g15Runner
$shaG14ScriptFin = Get-FileHashSha256 $g14Script
$shaG14RunnerFin = Get-FileHashSha256 $g14Runner
$shaG19ScriptFin = Get-FileHashSha256 $g19Script
$shaG19RunnerFin = Get-FileHashSha256 $g19Runner

Write-Host "SHA-256 G17 Script fin:    $shaG17Fin"
if ($shaG17Inicio -ne $shaG17Fin) {
    Write-Host "ADVERTENCIA: test_tc_m05_g17.py cambio durante la ejecucion!" -ForegroundColor Red
} else {
    Write-Host "G17 Script integro: OK"
}

if ($shaG16ScriptIni -ne $shaG16ScriptFin -or $shaG16RunnerIni -ne $shaG16RunnerFin) {
    Write-Host "ERROR CRITICO: Los archivos de G16 fueron modificados!" -ForegroundColor Red
    exit 5
} else {
    Write-Host "G16 integro: OK"
}

if ($shaG15ScriptIni -ne $shaG15ScriptFin -or $shaG15RunnerIni -ne $shaG15RunnerFin) {
    Write-Host "ERROR CRITICO: Los archivos de G15 fueron modificados!" -ForegroundColor Red
    exit 5
} else {
    Write-Host "G15 integro: OK"
}

if ($shaG14ScriptIni -ne $shaG14ScriptFin -or $shaG14RunnerIni -ne $shaG14RunnerFin) {
    Write-Host "ERROR CRITICO: Los archivos de G14 fueron modificados!" -ForegroundColor Red
    exit 5
} else {
    Write-Host "G14 integro: OK"
}

if ($shaG19ScriptIni -ne $shaG19ScriptFin -or $shaG19RunnerIni -ne $shaG19RunnerFin) {
    Write-Host "ERROR CRITICO: Los archivos de G19 fueron modificados!" -ForegroundColor Red
    exit 5
} else {
    Write-Host "G19 integro: OK"
}

# --- Post-corrida de seguridad: escaneo de secretos
$patrones = New-Object System.Collections.Generic.List[string]
$varsSecretos = @(
    'TEST_SANDBOX_SECRET',
    'TEST_ADMIN_PASSWORD', 'TEST_ADMIN_EMAIL',
    'TEST_VET_PASSWORD', 'TEST_VET_EMAIL',
    'TEST_PROD_PASSWORD', 'TEST_PROD_EMAIL',
    'TEST_ING_PASSWORD', 'TEST_ING_EMAIL'
)
foreach ($varNom in $varsSecretos) {
    $v = [Environment]::GetEnvironmentVariable($varNom, 'Process')
    if (-not [string]::IsNullOrWhiteSpace($v) -and $v.Length -ge 4) {
        $patrones.Add($v)
        if ($v.Length -gt 20) {
            $patrones.Add($v.Substring($v.Length - 20))
        }
    }
}
$patrones.Add('eyJ')

$utf8 = New-Object System.Text.UTF8Encoding($false)
$artefactos = @(Get-ChildItem -LiteralPath $staging -File -Recurse)

function Contar-Secretos([string]$texto) {
    $n = 0
    foreach ($p in $patrones) {
        if ($texto.Contains($p)) { $n++ }
    }
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

if ($quedan -gt 0) {
    Write-Host 'ARTEFACTOS CON SECRETOS: NO PROMOVER' -ForegroundColor Red
    exit 4
}
Write-Host 'Escaneo de secretos en staging: LIMPIO (0 secretos)'

# --- Promocion Condicionada
$jsonPath = Join-Path $staging 'resultado_TC-M05-G17.json'
$promover = $false

if ($codigo -eq 0 -and (Test-Path -LiteralPath $jsonPath)) {
    try {
        $jsonContenido = Get-Content -LiteralPath $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($jsonContenido.summary.veredicto -eq 'Aprobado' -and $jsonContenido.summary.falla -eq 0 -and $jsonContenido.summary.ok -eq 7) {
            $promover = $true
        }
    } catch {
        Write-Host "Error parseando JSON de resultado: $_" -ForegroundColor Yellow
    }
}

if ($promover) {
    Write-Host 'Criterios cumplidos: Promoviendo artefactos a resultados/...' -ForegroundColor Green
    Copy-Item -LiteralPath $html -Destination (Join-Path $resultadosDir 'resultado_TC-M05-G17.html') -Force
    Copy-Item -LiteralPath $jsonPath -Destination (Join-Path $resultadosDir 'resultado_TC-M05-G17.json') -Force
    Write-Host "Promocion completada exitosamente en $resultadosDir" -ForegroundColor Green
} else {
    Write-Host 'Condiciones de promocion no cumplidas; NO se promovio a resultados/' -ForegroundColor Yellow
}

