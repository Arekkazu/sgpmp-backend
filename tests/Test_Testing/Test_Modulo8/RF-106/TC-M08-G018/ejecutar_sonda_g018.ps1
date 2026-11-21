# | 2026-11-19 | Juan Sebastian Gutierrez | Runner de la SONDA de datos de TC-M08-G018: solo lectura, sin checkpoints, salida en evidencias\sonda-<ts> |
# | 2026-11-19 | Juan Sebastian Gutierrez | -CuentaVet M08: usa TEST_M08_VET_EMAIL/TEST_M08_VET_PASSWORD (Veterinario de la finca 494) sin tocar TEST_VET_* |
#
# Uso (desde la carpeta del caso, PowerShell 5.1):   .\ejecutar_sonda_g018.ps1
# No genera reporte para el dashboard. Escribe sonda_TC-M08-G018.txt con el estado del activo A por fuente y los
# candidatos para CP-08 (activo de otra finca) y CP-10 (activo dado de baja).
#
# Codigos de salida: 0 sonda completa | 2 configuracion local | 3 ABORT (precondicion en TEST) | 4 hallazgos en el escaneo
#                    de secretos | 5 cierre del sandbox distinto de 200 "Rollback exitoso" | 6 resultados\ cambio
param(
  [int]$IdActivoA = 885,
  [int]$IdActivoOtraFinca = 2562,
  [ValidateSet('TEST', 'M08')][string]$CuentaVet = 'TEST'
)
$ErrorActionPreference = 'Stop'
$kVetEmail = if ($CuentaVet -eq 'M08') { 'TEST_M08_VET_EMAIL' } else { 'TEST_VET_EMAIL' }
$kVetPass = if ($CuentaVet -eq 'M08') { 'TEST_M08_VET_PASSWORD' } else { 'TEST_VET_PASSWORD' }
$tc = 'TC-M08-G018'
$raiz = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $raiz '..\..\..\..\..')).Path
$envFile = Join-Path $repo '.env.test'
$col = Join-Path $raiz 'tc-m08-g018-sonda.postman_collection.json'
$resultados = Join-Path $raiz 'resultados'

function Salir([int]$codigo, [string]$motivo) {
  Write-Host "[$tc] salida $codigo : $motivo"
  exit $codigo
}
function ShaCarpeta([string]$ruta) {
  if (-not (Test-Path $ruta)) { return '(no existe)' }
  $lineas = Get-ChildItem -Path $ruta -File -Recurse | Sort-Object FullName | ForEach-Object {
    $_.FullName.Substring($ruta.Length) + ' ' + (Get-FileHash -Algorithm SHA256 -Path $_.FullName).Hash
  }
  return ($lineas -join "`n")
}
function CerrarTraza([string]$b, $lista) {
  $t = $b.Trim()
  if ($t.StartsWith("'") -and $t.EndsWith("'")) { $t = $t.Substring(1, $t.Length - 2) }
  if ($t -match '^(SONDA|PRE|ABORT|CIERRE)\|') { $lista.Add($t) }
}
function Escribir([string]$ruta, [string]$texto) {
  [System.IO.File]::WriteAllText($ruta, $texto, (New-Object System.Text.UTF8Encoding $false))
}

# ---- precondiciones locales
if (-not (Test-Path $envFile)) { Salir 2 "no existe $envFile" }
if (-not (Test-Path $col)) { Salir 2 "no existe la coleccion $col" }
$newman = Get-Command newman.cmd -ErrorAction SilentlyContinue
if (-not $newman) { $newman = Get-Command newman -ErrorAction SilentlyContinue }
if (-not $newman) { Salir 2 'newman no esta instalado' }
foreach ($prohibido in 930, 900, 901, 825) { if ($IdActivoA -eq $prohibido -or $IdActivoOtraFinca -eq $prohibido) { Salir 2 "activo $prohibido prohibido" } }

# ---- credenciales: solo en memoria
$cfg = @{}
foreach ($l in Get-Content -Path $envFile -Encoding UTF8) {
  if ($l -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
    $cfg[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'")
  }
}
foreach ($k in 'TEST_BASE_URL', 'TEST_SANDBOX_SECRET', $kVetEmail, $kVetPass, 'TEST_PRODUCER_EMAIL', 'TEST_PRODUCER_PASSWORD') {
  if (-not $cfg[$k]) { Salir 2 "falta $k en .env.test" }
}

# ---- staging
$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
$staging = Join-Path $raiz "evidencias\sonda-$ts"
New-Item -ItemType Directory -Path $staging -Force | Out-Null
$consola = Join-Path $staging "consola_sonda_$tc.txt"
$runId = "qa-m08-g018-sonda-$ts"
$shaResultadosAntes = ShaCarpeta $resultados
$shaCol = (Get-FileHash -Algorithm SHA256 -Path $col).Hash
$shaRunner = (Get-FileHash -Algorithm SHA256 -Path $PSCommandPath).Hash

$a = @(
  'run', $col, '-r', 'cli', '--disable-unicode', '--color', 'off',
  '--env-var', ('base_url=' + $cfg['TEST_BASE_URL'].TrimEnd('/')),
  '--env-var', ('sandbox_secret=' + $cfg['TEST_SANDBOX_SECRET']),
  '--env-var', ('run_id=' + $runId),
  '--env-var', ('correo_vet=' + $cfg[$kVetEmail]),
  '--env-var', ('contrasena_vet=' + $cfg[$kVetPass]),
  '--env-var', ('correo_productor=' + $cfg['TEST_PRODUCER_EMAIL']),
  '--env-var', ('contrasena_productor=' + $cfg['TEST_PRODUCER_PASSWORD']),
  '--env-var', ('id_activo_a=' + $IdActivoA),
  '--env-var', ('id_activo_otra_finca=' + $IdActivoOtraFinca)
)

# ---- ejecucion unica
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:NO_COLOR = '1'; $env:FORCE_COLOR = '0'
$inicio = Get-Date
$ErrorActionPreference = 'Continue'
& $newman.Source @a 2>&1 | ForEach-Object { "$_" } | Out-File -Encoding utf8 -FilePath $consola
$rcNewman = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
$duracion = [int]((Get-Date) - $inicio).TotalSeconds
$a = $null

# ---- trazas (bloques de console.log partidos por el ancho de la consola)
$lineas = Get-Content -Path $consola -Encoding UTF8
$trazas = New-Object System.Collections.Generic.List[string]
$bloque = $null
foreach ($l in $lineas) {
  if ($l -match '^\s*\| (.*)$') {
    $seg = $matches[1]
    if ($null -ne $bloque -and $seg.StartsWith("'") -and $bloque.TrimEnd().EndsWith("'")) { CerrarTraza $bloque $trazas; $bloque = $null }
    if ($null -eq $bloque) { $bloque = $seg } else { $bloque += $seg }
  } elseif ($null -ne $bloque) {
    CerrarTraza $bloque $trazas
    $bloque = $null
  }
}
if ($null -ne $bloque) { CerrarTraza $bloque $trazas }
Escribir (Join-Path $staging "sonda_$tc.txt") (($trazas -join "`r`n") + "`r`n")

# ---- escaneo de secretos (solo reporta; no reescribe nada)
$patrones = [ordered]@{}
$patrones['contrasena_vet'] = $cfg[$kVetPass]
$patrones['contrasena_productor'] = $cfg['TEST_PRODUCER_PASSWORD']
$patrones['secreto_sandbox'] = $cfg['TEST_SANDBOX_SECRET']
$patrones['correo_vet'] = $cfg[$kVetEmail]
$patrones['correo_productor'] = $cfg['TEST_PRODUCER_EMAIL']
foreach ($k in $kVetPass, 'TEST_PRODUCER_PASSWORD', 'TEST_SANDBOX_SECRET') {
  $v = $cfg[$k]
  if ($v.Length -ge 20) { $patrones["ultimos20_$k"] = $v.Substring($v.Length - 20) }
}
$patrones['prefijo_jwt'] = 'ey' + 'J'
$hallazgos = New-Object System.Collections.Generic.List[string]
$archivos = Get-ChildItem -Path $staging -File | Where-Object { $_.Extension -in '.html', '.txt', '.json', '.log', '.xml', '.md' }
foreach ($f in $archivos) {
  $contenido = [System.IO.File]::ReadAllText($f.FullName)
  foreach ($k in $patrones.Keys) {
    $p = $patrones[$k]
    if ([string]::IsNullOrEmpty($p)) { continue }
    $n = ([regex]::Matches($contenido, [regex]::Escape($p))).Count
    if ($n -gt 0) { $hallazgos.Add("$($f.Name): $k x$n") }
  }
}
$cfg.Clear(); $patrones.Clear()
$textoEscaneo = "Archivos revisados: $($archivos.Count)`r`nPatrones: contrasenas, secreto del sandbox, ultimos 20 caracteres, correos, prefijo JWT`r`n"
if ($hallazgos.Count -eq 0) { $textoEscaneo += "Hallazgos: 0`r`n" }
else { $textoEscaneo += "Hallazgos: $($hallazgos.Count)`r`n" + ($hallazgos -join "`r`n") + "`r`n" }
Escribir (Join-Path $staging "escaneo_secretos_sonda_$tc.txt") $textoEscaneo

# ---- integridad de resultados\ y cierre del sandbox
$shaResultadosDespues = ShaCarpeta $resultados
$cierre = @($trazas | Where-Object { $_ -like 'CIERRE|*' })
$cierreOk = ($cierre.Count -eq 1 -and $cierre[0] -like 'CIERRE|200|Rollback exitoso|*')
$abort = @($trazas | Where-Object { $_ -like 'ABORT|*' })
$resumen = @(
  "Sonda de $tc   run_id: $runId   activo A: $IdActivoA   otra finca: $IdActivoOtraFinca   cuenta veterinario: $kVetEmail",
  "Inicio: $($inicio.ToString('yyyy-MM-dd HH:mm:ss'))   Duracion: $duracion s   newman exit: $rcNewman",
  "Trazas: $($trazas.Count)   ABORT: $($abort.Count)   Cierre: $(if ($cierre.Count) { $cierre[0] } else { 'no encontrado' })",
  "Escaneo de secretos: $($hallazgos.Count) hallazgos",
  "resultados\ sin cambios: $($shaResultadosAntes -eq $shaResultadosDespues)",
  "SHA-256 coleccion: $shaCol",
  "SHA-256 runner:    $shaRunner"
) -join "`r`n"
Escribir (Join-Path $staging "resumen_sonda_$tc.txt") ($resumen + "`r`n")
Write-Host $resumen

if ($shaResultadosAntes -ne $shaResultadosDespues) { Salir 6 'resultados\ cambio durante la sonda' }
if ($hallazgos.Count -gt 0) { Salir 4 'hay hallazgos en el escaneo de secretos' }
if ($abort.Count -gt 0) { Salir 3 'precondicion no cumplida en TEST' }
if (-not $cierreOk) { Salir 5 'el cierre del sandbox no respondio 200 Rollback exitoso' }
Salir 0 'sonda completa'
