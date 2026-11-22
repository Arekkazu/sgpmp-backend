# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-11-19 | Juan Manuel      | TC-M08: runner propio de M08 (no toca el runner comun) |
# | 2026-11-21 | Juan Manuel      | TC-M08: token del broker (G015)                        |
# Runner de los casos de M08. Uso (desde tests\Test_Testing\Test_Modulo8):
#   .\correr_newman_m08.ps1 -Caso G001 -Rf RF-103
#
# Igual que el runner de M05: NO guarda nada en disco ni en el registro de Windows. Lee la coleccion,
# detecta que variables usa y pide solo las que faltan (claves y secretos ocultos). Lo escrito vive
# unicamente en la terminal abierta (variables QA_* del proceso).
param(
  [Parameter(Mandatory=$true)][string]$Caso,
  [Parameter(Mandatory=$true)][string]$Rf,
  [string]$Version = ''
)

$id = "TC-M08-$Caso"
$Ruta = Join-Path $PSScriptRoot "$Rf\$id"
$col = Join-Path $Ruta ("tc-m08-" + $Caso.ToLower() + ".json")
if (-not (Test-Path $col)) { Write-Host "No existe $col" -ForegroundColor Red; exit 1 }

# variable de la coleccion -> (secreto?, valor por defecto NO sensible). Cuentas del DBA del 2026-11-19.
$def = [ordered]@{
  sandbox_secret         = @{S=$true;  D=''}
  correo_admin           = @{S=$false; D='admin.rol@gmail.com'}
  contrasena_admin       = @{S=$true;  D=''}
  correo_productor       = @{S=$false; D='qa.m08.productor@sgpmp-test.com'}
  contrasena_productor   = @{S=$true;  D=''}
  correo_veterinario     = @{S=$false; D='qa.m08.veterinario@sgpmp-test.com'}
  contrasena_veterinario = @{S=$true;  D=''}
  correo_contador        = @{S=$false; D='qa.m08.contador@sgpmp-test.com'}
  contrasena_contador    = @{S=$true;  D=''}
  correo_ingeniero       = @{S=$false; D='qa.m08.ingeniero@sgpmp-test.com'}
  contrasena_ingeniero   = @{S=$true;  D=''}
  broker_token           = @{S=$true;  D=''}
  correo_otra_finca      = @{S=$false; D='productor@gmail.com'}
  correo_bandeja         = @{S=$false; D='qa.m08.productor.bandeja@sgpmp-test.com'}
  contrasena_bandeja     = @{S=$true;  D=''}
  contrasena_otra_finca  = @{S=$true;  D=''}
  correo_gestor          = @{S=$false; D='gestor.granja@gmail.com'}
  contrasena_gestor      = @{S=$true;  D=''}
}

$texto = Get-Content $col -Raw
$args2 = @()
foreach ($k in $def.Keys) {
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
# Redacta secretos (JWT, Bearer, X-Sandbox-Secret, contrasena del login) con el limpiador comun (no se modifica)
if (Test-Path $html) {
  $limpiador = Join-Path (Split-Path $PSScriptRoot -Parent) 'limpiar_reporte.py'
  python $limpiador $html
  if ($LASTEXITCODE -ne 0) { Write-Host 'ATENCION: no se pudo limpiar el reporte; NO lo subas a Git.' -ForegroundColor Red }
}
Write-Host "Reporte: $html" -ForegroundColor Cyan
exit $rc
