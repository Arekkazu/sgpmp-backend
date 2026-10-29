# Uso (desde tests\Test_Testing):
#   .\correr_newman.ps1 -Caso G69                  (Modulo 3, RF-57 por defecto)
#   .\correr_newman.ps1 -Caso G73 -Rf RF-59
#   .\correr_newman.ps1 -Caso G12 -Modulo 4 -Rf RF-70
#   .\correr_newman.ps1 -Caso G026 -Modulo 4 -Rf RF-68 -Version v2.0   (genera resultado_TC-M04-G026_v2.0.html)
#
# NO guarda nada en disco ni en el registro de Windows. Lee la coleccion, detecta que variables
# usa y pide solo las que faltan (las claves y secretos se escriben ocultos). Lo que escribas
# vive unicamente en la terminal abierta: si reutilizas la misma terminal para el siguiente
# caso, ya no te vuelve a pedir nada; al cerrarla, todo desaparece.
param(
  [Parameter(Mandatory=$true)][string]$Caso,
  [int]$Modulo = 3,
  [string]$Rf = 'RF-57',
  [string]$Ruta = '',
  [string]$Version = ''
)

$id = "TC-M0$Modulo-$Caso"
if (-not $Ruta) { $Ruta = Join-Path $PSScriptRoot "Test_Modulo$Modulo\$Rf\$id" }
$col = Join-Path $Ruta ("tc-m0$Modulo-" + $Caso.ToLower() + ".json")
if (-not (Test-Path $col)) { Write-Host "No existe $col" -ForegroundColor Red; exit 1 }

# variable de la coleccion -> (secreto?, valor por defecto NO sensible)
$def = [ordered]@{
  sandbox_secret        = @{S=$true;  D=''}
  broker_service_token  = @{S=$true;  D=''}
  correo_admin          = @{S=$false; D='admin@pecuaria.co'}
  contrasena_admin      = @{S=$true;  D=''}
  correo_productor      = @{S=$false; D='daniiella.vargass@gmail.com'}
  contrasena_productor  = @{S=$true;  D=''}
  correo_veterinario    = @{S=$false; D='mariajosecastillovargas57@gmail.com'}
  contrasena_veterinario= @{S=$true;  D=''}
  correo_ingeniero      = @{S=$false; D='ingedecampo6@gmail.com'}
  contrasena_ingeniero  = @{S=$true;  D=''}
  device_id             = @{S=$false; D='339'}
  serial                = @{S=$false; D='QA-SEMILLA-ADM-M03-HIST-01'}
  sensor_temperatura_ambiental = @{S=$false; D='525'}
  sensor_humedad_relativa      = @{S=$false; D='526'}
  sensor_oxigeno_disuelto      = @{S=$false; D='3'}
  device_id_oxigeno            = @{S=$false; D='1'}
  serial_oxigeno               = @{S=$false; D='IOT-EST01-HLA-001'}
}

$texto = Get-Content $col -Raw
$args2 = @()
foreach ($k in $def.Keys) {
  # la coleccion usa la variable como {{nombre}} o dentro de un script como 'nombre' / "nombre"
  $e = [regex]::Escape($k)
  if ($texto -notmatch "(\{\{$e\}\}|['\\""]$e['\\""])") { continue }
  $envName = "QA_$($k.ToUpper())"
  $v = [Environment]::GetEnvironmentVariable($envName, 'Process')
  if (-not $v) {
    if ($def[$k].S) {
      $sec = Read-Host "$k" -AsSecureString
      $v = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    } else {
      $v = Read-Host "$k [$($def[$k].D)]"
      if ([string]::IsNullOrWhiteSpace($v)) { $v = $def[$k].D }
    }
    [Environment]::SetEnvironmentVariable($envName, $v, 'Process')   # solo esta terminal
  }
  if (-not $v) { Write-Host "Falta $k" -ForegroundColor Red; exit 1 }
  $args2 += '--env-var'; $args2 += "$k=$v"
}

New-Item -ItemType Directory -Force -Path (Join-Path $Ruta 'resultados') | Out-Null
$sufijo = if ($Version) { "_$Version" } else { "" }
$html = Join-Path $Ruta "resultados\resultado_$id$sufijo.html"
$titulo = if ($Version) { "$id $Version" } else { $id }
Push-Location $Ruta
newman run $col -r "cli,htmlextra" --reporter-htmlextra-export $html --reporter-htmlextra-title $titulo @args2
$rc = $LASTEXITCODE
Pop-Location
# Redacta secretos (JWT, Bearer, X-Sandbox-Secret, contrasena del login) del reporte para poder subirlo a Git
if (Test-Path $html) {
  $limpiador = Join-Path $PSScriptRoot 'limpiar_reporte.py'
  python $limpiador $html
  if ($LASTEXITCODE -ne 0) { Write-Host 'ATENCION: no se pudo limpiar el reporte; NO lo subas a Git.' -ForegroundColor Red }
}
Write-Host "Reporte: $html" -ForegroundColor Cyan
exit $rc
