<#
.SYNOPSIS
  Runner de ejecucion para TC-M05-G18 (RF-76: Integracion con RF-44 y fallas de persistencia).

.DESCRIPTION
  - Carga .env.test en variables de entorno del proceso sin imprimir valores.
  - Crea evidencias\run-<yyyyMMdd-HHmmss>\ y exporta G18_RUN_DIR.
  - Ejecuta pytest (-p no:randomly -v --tb=short) generando:
      resultado_TC-M05-G18.html (--self-contained-html),
      junit_TC-M05-G18.xml y pytest.log (UTF-8).
  - Ejecuta escaneo final de secretos sobre <run>\ reportando "N coincidencias".
  - No escribe ni copia archivos hacia resultados\.
#>
$ErrorActionPreference = 'Stop'

$tcDir   = $PSScriptRoot
$repo    = (Resolve-Path -LiteralPath (Join-Path $tcDir '..\..\..\..\..')).Path
$prueba  = Join-Path $tcDir 'test_tc_m05_g18.py'
$envFile = Join-Path $repo '.env.test'
$python  = Join-Path $repo '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $prueba)) {
    Write-Host "FALTA el script de prueba: $prueba" -ForegroundColor Red
    exit 2
}
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "FALTA Python del entorno virtual: $python" -ForegroundColor Red
    exit 2
}

if (Test-Path -LiteralPath $envFile) {
    foreach ($linea in Get-Content -LiteralPath $envFile -Encoding UTF8) {
        $t = $linea.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $idx = $t.IndexOf('=')
        if ($idx -lt 1) { continue }
        $nombre = $t.Substring(0, $idx).Trim()
        $valor  = $t.Substring($idx + 1).Trim()
        if ($valor.Length -ge 2 -and (
                ($valor.StartsWith('"') -and $valor.EndsWith('"')) -or
                ($valor.StartsWith("'") -and $valor.EndsWith("'")))) {
            $valor = $valor.Substring(1, $valor.Length - 2)
        }
        if (-not [string]::IsNullOrEmpty($nombre)) {
            [Environment]::SetEnvironmentVariable($nombre, $valor, 'Process')
        }
    }
}

$marca  = Get-Date -Format 'yyyyMMdd-HHmmss'
$runDir = Join-Path $tcDir "evidencias\run-$marca"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$env:G18_RUN_DIR = $runDir
$env:PYTHONUTF8  = '1'
$env:PYTHONPATH  = '.'

$html = Join-Path $runDir 'resultado_TC-M05-G18.html'
$xml  = Join-Path $runDir 'junit_TC-M05-G18.xml'
$log  = Join-Path $runDir 'pytest.log'

$argumentos = @(
    '-m', 'pytest', $prueba,
    '-p', 'no:randomly',
    '-v',
    '--tb=short',
    "--html=$html", '--self-contained-html',
    "--junitxml=$xml"
)

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

# --- Escaneo final de secretos sobre todos los archivos de <run>\ ---
$clave   = [Environment]::GetEnvironmentVariable('TEST_ADMIN_PASSWORD', 'Process')
$secreto = [Environment]::GetEnvironmentVariable('TEST_SANDBOX_SECRET', 'Process')

$patrones = New-Object System.Collections.Generic.List[string]
foreach ($v in @($clave, $secreto)) {
    if (-not [string]::IsNullOrEmpty($v)) {
        if (-not $patrones.Contains($v)) { $patrones.Add($v) }
        if ($v.Length -gt 20) {
            $cola = $v.Substring($v.Length - 20)
            if (-not [string]::IsNullOrEmpty($cola) -and -not $patrones.Contains($cola)) {
                $patrones.Add($cola)
            }
        }
    }
}
$jwtPrefix = 'ey' + 'J'
if (-not $patrones.Contains($jwtPrefix)) { $patrones.Add($jwtPrefix) }

$utf8 = New-Object System.Text.UTF8Encoding($false)
$archivos = @(Get-ChildItem -LiteralPath $runDir -File -Recurse)
[int]$coincidencias = 0

foreach ($archivo in $archivos) {
    $texto = [IO.File]::ReadAllText($archivo.FullName, $utf8)
    foreach ($patron in $patrones) {
        if (-not [string]::IsNullOrEmpty($patron)) {
            $coincidencias += [Regex]::Matches($texto, [Regex]::Escape($patron)).Count
        }
    }
}

$clave = $null
$secreto = $null
$patrones.Clear()

Write-Host ''
Write-Host "Directorio de corrida: $runDir"
Write-Host "Escaneo de secretos: $coincidencias coincidencias"

if ($coincidencias -gt 0) {
    Write-Host 'ALERTA: artefactos con posibles secretos detectados. NO PROMOVER.' -ForegroundColor Red
    exit 4
}

if ($null -eq $codigo) { exit 1 }
exit $codigo

