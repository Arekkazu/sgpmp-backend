# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-11-07 | Juan Manuel      | TC-M05: runner propio de M05 (no toca el runner comun) |
# Runner de los casos de M05 (RF-74, RF-75, RF-78, RF-79). Uso (desde tests\Test_Testing\Test_Modulo5):
#   .\correr_newman_m05.ps1 -Caso G01 -Rf RF-74
#   .\correr_newman_m05.ps1 -Caso G26 -Rf RF-78
#
# Igual que tests\Test_Testing\correr_newman.ps1, pero con las variables y cuentas de M05:
# NO guarda nada en disco ni en el registro de Windows. Lee la coleccion, detecta que variables
# usa y pide solo las que faltan (las claves y secretos se escriben ocultos). Lo que escribas
# vive unicamente en la terminal abierta; al cerrarla, todo desaparece.
param(
  [Parameter(Mandatory=$true)][string]$Caso,
  [Parameter(Mandatory=$true)][string]$Rf,
  [string]$Version = ''
)

$id = "TC-M05-$Caso"
$Ruta = Join-Path $PSScriptRoot "$Rf\$id"
$col = Join-Path $Ruta ("tc-m05-" + $Caso.ToLower() + ".json")
if (-not (Test-Path $col)) { Write-Host "No existe $col" -ForegroundColor Red; exit 1 }

# variable de la coleccion -> (secreto?, valor por defecto NO sensible). Cuentas QA de TEST entregadas el 2026-11-06.
$def = [ordered]@{
  sandbox_secret         = @{S=$true;  D=''}
  correo_admin           = @{S=$false; D='admin.rol@gmail.com'}
  contrasena_admin       = @{S=$true;  D=''}
  correo_productor       = @{S=$false; D='productor@gmail.com'}
  contrasena_productor   = @{S=$true;  D=''}
  correo_veterinario     = @{S=$false; D='veterinario@gmail.com'}
  contrasena_veterinario = @{S=$true;  D=''}
  correo_ingeniero       = @{S=$false; D='ingeniero.campo@gmail.com'}
  contrasena_ingeniero   = @{S=$true;  D=''}
  correo_contador        = @{S=$false; D='contador@gmail.com'}
  contrasena_contador    = @{S=$true;  D=''}
  correo_gestor          = @{S=$false; D='gestor.granja@gmail.com'}
  contrasena_gestor      = @{S=$true;  D=''}
  correo_revisor         = @{S=$false; D='revisor.fiscal@gmail.com'}
  contrasena_revisor     = @{S=$true;  D=''}
  id_activo_a            = @{S=$false; D='825'}
  id_activo_b            = @{S=$false; D='328'}
  id_activo_pob_cero     = @{S=$false; D='462'}
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
# Redacta secretos (JWT, Bearer, X-Sandbox-Secret, contrasena del login) del reporte con el limpiador comun (no se modifica)
if (Test-Path $html) {
  $limpiador = Join-Path (Split-Path $PSScriptRoot -Parent) 'limpiar_reporte.py'
  python $limpiador $html
  if ($LASTEXITCODE -ne 0) { Write-Host 'ATENCION: no se pudo limpiar el reporte; NO lo subas a Git.' -ForegroundColor Red }
}
Write-Host "Reporte: $html" -ForegroundColor Cyan
exit $rc
