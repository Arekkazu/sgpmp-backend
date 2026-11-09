# | Fecha      | Nombre                   | Que se hizo                                                          |
# |------------|--------------------------|----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G14 RF-76: runner Pytest con staging de evidencias            |
<#
.SYNOPSIS
  Ejecuta TC-M05-G14 (RF-76, POST /suministros/medicamentos) contra TEST bajo sandbox transaccional.

.DESCRIPTION
  - Carga .env.test del repo en las variables de entorno del PROCESO (sin imprimir valores).
  - Verifica TEST_BASE_URL, TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD y TEST_SANDBOX_SECRET.
  - Crea el staging evidencias\run-<yyyyMMdd-HHmmss>\ y define TEST_EVIDENCE_DIR,
    PYTHONUTF8=1 y PYTHONPATH=".".
  - Ejecuta pytest (orden de archivo, -p no:randomly) con reporte HTML autocontenido,
    JUnit XML y log de consola en UTF-8, todo dentro del staging.
  - NO escribe ni copia nada en resultados\: la promocion del reporte es manual.

.PARAMETER Reintento
  Si es mayor que 0, los reportes llevan el sufijo _reintentoN.

.PARAMETER ActivoId
  Si es mayor que 0, define TEST_M05_ACTIVO_ID solo para este proceso (no toca .env.test).

.EXAMPLE
  .\ejecutar_tc_m05_g14.ps1
  .\ejecutar_tc_m05_g14.ps1 -Reintento 1 -ActivoId 57

.NOTES
  Exit codes: 2 falta archivo, 3 falta variable, 4 artefactos con secretos (NO PROMOVER),
  en otro caso el exit code de pytest.
#>
param(
    [int]$Reintento = 0,
    [int]$ActivoId = 0
)

$ErrorActionPreference = 'Stop'

# --- Rutas relativas a la ubicacion de este script (TC -> RF-76 -> Test_Modulo5 -> Test_Testing -> tests -> repo)
$tcDir   = $PSScriptRoot
$repo    = (Resolve-Path -LiteralPath (Join-Path $tcDir '..\..\..\..\..')).Path
$prueba  = Join-Path $tcDir 'test_tc_m05_g14.py'
$envFile = Join-Path $repo '.env.test'

if (-not (Test-Path -LiteralPath $prueba)) {
    Write-Host "FALTA el script de prueba: $prueba" -ForegroundColor Red
    exit 2
}
if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Host "FALTA .env.test en la raiz del repo ($repo)" -ForegroundColor Red
    exit 2
}

# --- Carga de .env.test en el proceso: linea a linea, sin imprimir valores
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

# --- Verificacion de variables obligatorias (solo OK/FALTA)
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

# --- Activo de prueba (solo para este proceso)
if ($ActivoId -gt 0) {
    [Environment]::SetEnvironmentVariable('TEST_M05_ACTIVO_ID', "$ActivoId", 'Process')
}
$activoEfectivo = [Environment]::GetEnvironmentVariable('TEST_M05_ACTIVO_ID', 'Process')
if ([string]::IsNullOrWhiteSpace($activoEfectivo)) { $activoEfectivo = '930 (defecto del script)' }
Write-Host "ActivoId: $activoEfectivo"

# --- Staging de la corrida
$sufijo  = if ($Reintento -gt 0) { "_reintento$Reintento" } else { '' }
$marca   = Get-Date -Format 'yyyyMMdd-HHmmss'
$staging = Join-Path $tcDir "evidencias\run-$marca"
New-Item -ItemType Directory -Force -Path $staging | Out-Null

$env:TEST_EVIDENCE_DIR = $staging
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = '.'

$html = Join-Path $staging "resultado_TC-M05-G14$sufijo.html"
$xml  = Join-Path $staging "resultado_TC-M05-G14$sufijo.xml"
$log  = Join-Path $staging 'console_execution.log'

$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }

$argumentos = @(
    '-m', 'pytest', $prueba,
    '-p', 'no:randomly',
    '-v',
    '--tb=short',
    "--html=$html", '--self-contained-html',
    "--junitxml=$xml"
)

# --- Ejecucion (stderr de un nativo en PS 5.1 se convierte a texto; sin operador >)
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

# --- Conteo de tests ejecutados segun el JUnit XML
$ejecutados = 0
if (Test-Path -LiteralPath $xml) {
    try {
        [xml]$junit = Get-Content -LiteralPath $xml -Raw -Encoding UTF8
        $suites = @($junit.SelectNodes('//testsuite'))
        foreach ($s in $suites) {
            $ejecutados += [int]$s.tests - [int]$s.skipped
        }
    } catch {
        Write-Host "No se pudo leer el JUnit XML: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "No se genero el JUnit XML." -ForegroundColor Yellow
}

Write-Host ''
Write-Host "Staging de la corrida: $staging"
Write-Host "Tests ejecutados: $ejecutados"
if ($ejecutados -eq 0) {
    Write-Host 'ADVERTENCIA: la corrida no ejecuto ningun test (0 tests ejecutados).' -ForegroundColor Yellow
}
Write-Host "Exit code de pytest: $codigo"

# --- Post-corrida de seguridad: secretos completos, cola del secreto y prefijo de JWT
$clave   = [Environment]::GetEnvironmentVariable('TEST_ADMIN_PASSWORD', 'Process')
$secreto = [Environment]::GetEnvironmentVariable('TEST_SANDBOX_SECRET', 'Process')
$patrones = New-Object System.Collections.Generic.List[string]
foreach ($v in @($secreto, $clave)) { if (-not [string]::IsNullOrEmpty($v)) { $patrones.Add($v) } }
if ($secreto.Length -gt 20) { $patrones.Add($secreto.Substring($secreto.Length - 20)) }
$patrones.Add('eyJ')

$utf8 = New-Object System.Text.UTF8Encoding($false)
$artefactos = @(Get-ChildItem -LiteralPath $staging -File -Recurse |
    Where-Object { $_.Extension -in @('.html', '.xml', '.log', '.jsonl') })

function Contar-Secretos([string]$texto) {
    $n = 0
    foreach ($p in $patrones) { if ($texto.Contains($p)) { $n++ } }
    return $n
}

$quedan = 0
foreach ($a in $artefactos) {
    $texto = [IO.File]::ReadAllText($a.FullName, $utf8)
    if ((Contar-Secretos $texto) -gt 0) {
        foreach ($p in $patrones) { $texto = $texto.Replace($p, '***') }
        [IO.File]::WriteAllText($a.FullName, $texto, $utf8)
        Write-Host "Saneado: $($a.Name)" -ForegroundColor Yellow
        $revisado = [IO.File]::ReadAllText($a.FullName, $utf8)
        if ((Contar-Secretos $revisado) -gt 0) { $quedan++ }
    }
}
$clave = $null; $secreto = $null; $patrones.Clear()

if ($quedan -gt 0) {
    Write-Host 'ARTEFACTOS CON SECRETOS: NO PROMOVER' -ForegroundColor Red
    exit 4
}
Write-Host 'SEGURIDAD OK'
Write-Host 'Nada se copio a resultados\: revisar el staging y promover el reporte manualmente.'

if ($null -eq $codigo) { exit 1 }
exit $codigo
