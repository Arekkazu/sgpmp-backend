# | 2026-11-19 | Juan Sebastian Gutierrez | Runner de TC-M08-G018 (RF-106): Newman en staging, sin tocar resultados\, escaneo de secretos solo reporte |
# | 2026-11-19 | Juan Sebastian Gutierrez | v2 (ronda 1 parcial): se quita el activo de baja (CP-10 retirado), 12 checkpoints, trazas RETIRADO |
# | 2026-11-19 | Juan Sebastian Gutierrez | -CuentaVet M08: usa TEST_M08_VET_EMAIL/TEST_M08_VET_PASSWORD (Veterinario de la finca 494) sin tocar TEST_VET_* |
# | 2026-11-20 | Juan Sebastian Gutierrez | v3 (corrida oficial de la ronda 1): -IdActivoBaja (CP-10), 13 checkpoints, escaneo al final con reescaneo de resumen y escaneo |
# | 2026-11-23 | Juan Sebastian Gutierrez | v4 (reintento 1): 12 checkpoints con lista explicita de ids; el JSON propio lo genera el runner con convertir_json_g018.mjs (node) antes del resumen y del escaneo; no corre si ya existe el JSON en resultados\ |
#
# Uso (desde la carpeta del caso, PowerShell 5.1):
#   .\ejecutar_tc_m08_g018.ps1 -IdActivoOtraFinca 2556 -IdActivoBaja 2946 -CuentaVet TEST -Reintento 0   (ronda 1)
#   .\ejecutar_tc_m08_g018.ps1 -IdActivoOtraFinca 2556 -IdActivoBaja 2946 -CuentaVet TEST -Reintento 1   (reintento 1)
#
# Codigos de salida:
#   0 todos los checkpoints OK | 1 hay checkpoints FALLA (corrida valida) | 2 configuracion o precondicion local
#   3 corrida invalida (ABORT, ids de checkpoints distintos de los 12 del diseno o JSON no generado) | 4 hallazgos en el escaneo de secretos
#   5 el cierre del sandbox no respondio 200 "Rollback exitoso" | 6 resultados\ cambio durante la corrida
param(
  [Parameter(Mandatory = $true)][int]$IdActivoOtraFinca,
  [Parameter(Mandatory = $true)][int]$IdActivoBaja,
  [int]$IdActivoA = 885,
  [int]$Reintento = 0,
  [ValidateSet('TEST', 'M08')][string]$CuentaVet = 'TEST'
)
$ErrorActionPreference = 'Stop'
$kVetEmail = if ($CuentaVet -eq 'M08') { 'TEST_M08_VET_EMAIL' } else { 'TEST_VET_EMAIL' }
$kVetPass = if ($CuentaVet -eq 'M08') { 'TEST_M08_VET_PASSWORD' } else { 'TEST_VET_PASSWORD' }
$tc = 'TC-M08-G018'
$checkpointsEsperados = 12
$idsEsperados = @('CP-01', 'CP-02', 'CP-04', 'CP-05', 'CP-06a', 'CP-06b', 'CP-07a', 'CP-07b', 'CP-08', 'CP-09a', 'CP-10', 'CP-11')
$raiz = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $raiz '..\..\..\..\..')).Path
$envFile = Join-Path $repo '.env.test'
$col = Join-Path $raiz 'tc-m08-g018.postman_collection.json'
$conversor = Join-Path $raiz 'convertir_json_g018.mjs'
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
  if ($t -match '^(CP|OBS|PRE|RETIRADO|ABORT|CIERRE)\|') { $lista.Add($t) }
}
function Escribir([string]$ruta, [string]$texto) {
  [System.IO.File]::WriteAllText($ruta, $texto, (New-Object System.Text.UTF8Encoding $false))
}
function BuscarSecretos($lista, $pats) {
  $h = New-Object System.Collections.Generic.List[string]
  foreach ($f in $lista) {
    $contenido = [System.IO.File]::ReadAllText($f.FullName)
    foreach ($k in $pats.Keys) {
      $p = $pats[$k]
      if ([string]::IsNullOrEmpty($p)) { continue }
      $n = ([regex]::Matches($contenido, [regex]::Escape($p))).Count
      if ($n -gt 0) { $h.Add("$($f.Name): $k x$n") }
    }
  }
  return ,$h
}

# ---- precondiciones locales
if (-not (Test-Path $envFile)) { Salir 2 "no existe $envFile" }
if (-not (Test-Path $col)) { Salir 2 "no existe la coleccion $col" }
if (-not (Test-Path $conversor)) { Salir 2 "no existe $conversor" }
$node = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $node) { $node = Get-Command node -ErrorAction SilentlyContinue }
if (-not $node) { Salir 2 'node no esta en el PATH' }
$newman = Get-Command newman.cmd -ErrorAction SilentlyContinue
if (-not $newman) { $newman = Get-Command newman -ErrorAction SilentlyContinue }
if (-not $newman) { Salir 2 'newman no esta instalado' }
$null = & npm ls -g newman-reporter-htmlextra --depth=0 2>$null
if ($LASTEXITCODE -ne 0) { Salir 2 'falta newman-reporter-htmlextra (npm install -g newman-reporter-htmlextra)' }
if ($IdActivoOtraFinca -eq $IdActivoA -or $IdActivoBaja -eq $IdActivoA -or $IdActivoBaja -eq $IdActivoOtraFinca) {
  Salir 2 'el activo A, el de otra finca y el de baja deben ser distintos'
}
foreach ($prohibido in 930, 900, 901, 825) {
  if ($IdActivoA -eq $prohibido -or $IdActivoOtraFinca -eq $prohibido -or $IdActivoBaja -eq $prohibido) { Salir 2 "activo $prohibido prohibido" }
}

$sufijo = if ($Reintento -gt 0) { "_reintento$Reintento" } else { '' }
$nombreReporte = "resultado_$tc$sufijo.html"
if (Test-Path (Join-Path $resultados $nombreReporte)) { Salir 2 "ya existe resultados\$nombreReporte" }
$nombreJson = "resultado_$tc$sufijo.json"
if (Test-Path (Join-Path $resultados $nombreJson)) { Salir 2 "ya existe resultados\$nombreJson" }

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
$staging = Join-Path $raiz "evidencias\run-$ts"
New-Item -ItemType Directory -Path $staging -Force | Out-Null
$html = Join-Path $staging $nombreReporte
$consola = Join-Path $staging "consola_$tc$sufijo.txt"
$runId = "qa-m08-g018-$ts"
$shaResultadosAntes = ShaCarpeta $resultados
$shaCol = (Get-FileHash -Algorithm SHA256 -Path $col).Hash
$shaRunner = (Get-FileHash -Algorithm SHA256 -Path $PSCommandPath).Hash
$shaConversor = (Get-FileHash -Algorithm SHA256 -Path $conversor).Hash

$a = @(
  'run', $col, '-r', 'cli,htmlextra',
  '--reporter-htmlextra-export', $html,
  '--reporter-htmlextra-title', "$tc$sufijo",
  '--reporter-htmlextra-logs',
  '--reporter-htmlextra-skipHeaders', 'Authorization,X-Sandbox-Secret',
  '--reporter-htmlextra-hideRequestBody', 'Z00 Login Veterinario,Z50 Login Productor',
  '--reporter-htmlextra-hideResponseBody', 'Z00 Login Veterinario,Z01 Perfil Veterinario,Z50 Login Productor',
  '--disable-unicode', '--color', 'off',
  '--env-var', ('base_url=' + $cfg['TEST_BASE_URL'].TrimEnd('/')),
  '--env-var', ('sandbox_secret=' + $cfg['TEST_SANDBOX_SECRET']),
  '--env-var', ('run_id=' + $runId),
  '--env-var', ('correo_vet=' + $cfg[$kVetEmail]),
  '--env-var', ('contrasena_vet=' + $cfg[$kVetPass]),
  '--env-var', ('correo_productor=' + $cfg['TEST_PRODUCER_EMAIL']),
  '--env-var', ('contrasena_productor=' + $cfg['TEST_PRODUCER_PASSWORD']),
  '--env-var', ('id_activo_a=' + $IdActivoA),
  '--env-var', ('id_activo_otra_finca=' + $IdActivoOtraFinca),
  '--env-var', ('id_activo_baja=' + $IdActivoBaja)
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

# ---- checkpoints (una linea por asercion en la consola) y trazas (bloques de console.log partidos por el ancho)
$lineas = Get-Content -Path $consola -Encoding UTF8
$cps = New-Object System.Collections.Generic.List[string]
foreach ($l in $lineas) {
  if ($l -match '^\s+Pass\s+(CP-\S+ .*)$') { $cps.Add('OK    | ' + $matches[1]) }
  elseif ($l -match '^\s+\d+\.\s+(CP-\S+ .*)$') { $cps.Add('FALLA | ' + $matches[1]) }
}
$trazas = New-Object System.Collections.Generic.List[string]
$bloque = $null
foreach ($l in $lineas) {
  if ($l -match '^\s*\| (.*)$') {
    $seg = $matches[1]
    # Newman no separa dos console.log seguidos del mismo script: una linea que abre con comilla tras un bloque cerrado es otra traza
    if ($null -ne $bloque -and $seg.StartsWith("'") -and $bloque.TrimEnd().EndsWith("'")) { CerrarTraza $bloque $trazas; $bloque = $null }
    if ($null -eq $bloque) { $bloque = $seg } else { $bloque += $seg }
  } elseif ($null -ne $bloque) {
    CerrarTraza $bloque $trazas
    $bloque = $null
  }
}
if ($null -ne $bloque) { CerrarTraza $bloque $trazas }
$ok = @($cps | Where-Object { $_.StartsWith('OK') }).Count
$falla = @($cps | Where-Object { $_.StartsWith('FALLA') }).Count
Escribir (Join-Path $staging "checkpoints_$tc$sufijo.txt") (($cps -join "`r`n") + "`r`n")
Escribir (Join-Path $staging "trazas_$tc$sufijo.txt") (($trazas -join "`r`n") + "`r`n")

# ---- integridad de resultados\, cierre y validez: se escribe todo ANTES del escaneo para que el escaneo lo cubra
$shaResultadosDespues = ShaCarpeta $resultados
$cierre = @($trazas | Where-Object { $_ -like 'CIERRE|*' })
$cierreOk = ($cierre.Count -eq 1 -and $cierre[0] -like 'CIERRE|200|Rollback exitoso|*')
$abort = @($trazas | Where-Object { $_ -like 'ABORT|*' })
$idsObtenidos = @($cps | ForEach-Object { if ($_ -match '^(OK|FALLA)\s+\|\s+(CP-\S+)') { $matches[2] } })
$idsOk = (($idsObtenidos -join ',') -ceq ($idsEsperados -join ','))
$jsonOk = $false
$salidaConversor = '(no se ejecuto)'
if ($abort.Count -gt 0) { Escribir (Join-Path $staging 'RUN_INVALIDA.txt') ("ABORT: " + ($abort -join ' / ') + "`r`n") }
elseif (-not $idsOk) { Escribir (Join-Path $staging 'RUN_INVALIDA.txt') ("Checkpoints: $($cps.Count) de $checkpointsEsperados; ids=" + ($idsObtenidos -join ',') + "`r`n") }
else {
  # JSON propio (manual 2.1) desde el mismo staging, antes del resumen y del escaneo para que el escaneo lo cubra
  $ErrorActionPreference = 'Continue'
  $salidaConversor = ((& $node.Source $conversor $staging "$Reintento" $runId 2>&1 | ForEach-Object { "$_" }) -join ' ').Trim()
  $rcConversor = $LASTEXITCODE
  $ErrorActionPreference = 'Stop'
  $jsonOk = ($rcConversor -eq 0 -and (Test-Path (Join-Path $staging $nombreJson)))
  if (-not $jsonOk) { Escribir (Join-Path $staging 'RUN_INVALIDA.txt') ("JSON no generado (exit $rcConversor): $salidaConversor`r`n") }
}

$resumen = @(
  "Caso: $tc   Reintento: $Reintento   run_id: $runId",
  "Inicio: $($inicio.ToString('yyyy-MM-dd HH:mm:ss'))   Duracion: $duracion s   newman exit: $rcNewman",
  "Activos: A=$IdActivoA  otra_finca=$IdActivoOtraFinca  baja=$IdActivoBaja   Retirados: ninguno   Cuenta veterinario: $kVetEmail",
  "Checkpoints: total=$($cps.Count) (esperados $checkpointsEsperados)  OK=$ok  FALLA=$falla",
  "ABORT: $($abort.Count)   Cierre: $(if ($cierre.Count) { $cierre[0] } else { 'no encontrado' })",
  "resultados\ sin cambios: $($shaResultadosAntes -eq $shaResultadosDespues)",
  "SHA-256 coleccion: $shaCol",
  "SHA-256 runner:    $shaRunner",
  "SHA-256 conversor: $shaConversor",
  "JSON (staging): $(if ($jsonOk) { (Join-Path $staging $nombreJson) + ' SHA-256 ' + (Get-FileHash -Algorithm SHA256 -Path (Join-Path $staging $nombreJson)).Hash } else { 'no generado' })   conversor: $salidaConversor",
  "Reporte (staging): $html"
) -join "`r`n"
$rutaResumen = Join-Path $staging "resumen_$tc$sufijo.txt"
$rutaEscaneo = Join-Path $staging "escaneo_secretos_$tc$sufijo.txt"
Escribir $rutaResumen ($resumen + "`r`n")

# ---- escaneo de secretos AL FINAL (solo reporta; no reescribe nada)
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
$archivos = @(Get-ChildItem -Path $staging -File | Where-Object { $_.Extension -in '.html', '.txt', '.json', '.log', '.xml', '.md' })
$hallazgos = BuscarSecretos $archivos $patrones
$textoEscaneo = "Archivos revisados: $($archivos.Count) (incluye resumen_$tc$sufijo.txt)`r`nPatrones: contrasenas, secreto del sandbox, ultimos 20 caracteres, correos, prefijo JWT`r`n"
if ($hallazgos.Count -eq 0) { $textoEscaneo += "Hallazgos: 0`r`n" }
else { $textoEscaneo += "Hallazgos: $($hallazgos.Count)`r`n" + ($hallazgos -join "`r`n") + "`r`n" }
Escribir $rutaEscaneo $textoEscaneo
Escribir $rutaResumen ($resumen + "`r`nEscaneo de secretos: $($hallazgos.Count) hallazgos`r`n")
# reescaneo de los dos archivos escritos despues de la primera pasada
$reescaneo = BuscarSecretos @((Get-Item $rutaResumen), (Get-Item $rutaEscaneo)) $patrones
$cfg.Clear(); $patrones.Clear()
foreach ($x in $reescaneo) { $hallazgos.Add("reescaneo $x") }
Write-Host $resumen
Write-Host "Escaneo de secretos: $($hallazgos.Count) hallazgos (reescaneo de resumen y escaneo: $($reescaneo.Count))"
foreach ($x in $hallazgos) { Write-Host "  $x" }

if ($abort.Count -gt 0) { Salir 3 'precondicion no cumplida en TEST' }
if ($shaResultadosAntes -ne $shaResultadosDespues) { Salir 6 'resultados\ cambio durante la corrida' }
if ($hallazgos.Count -gt 0) { Salir 4 'hay hallazgos en el escaneo de secretos' }
if (-not $cierreOk) { Salir 5 'el cierre del sandbox no respondio 200 Rollback exitoso' }
if (-not $idsOk) { Salir 3 'checkpoints distintos de los 12 del diseno' }
if (-not $jsonOk) { Salir 3 'no se genero el JSON propio' }
if ($falla -gt 0) { Salir 1 "$falla checkpoint(s) FALLA" }
Salir 0 'todos los checkpoints OK'
