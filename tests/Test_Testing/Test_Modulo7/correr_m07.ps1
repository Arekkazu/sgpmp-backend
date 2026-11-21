# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-18 | badigod | TC-M07 RF-95/RF-101: colecciones Newman y redaccion de secretos |
# Ejecuta una coleccion de M07 (RF-95 / RF-101) con Newman y deja el reporte limpio de secretos.
#
# Uso (desde tests\Test_Testing\Test_Modulo7):
#   .\correr_m07.ps1 -Caso G001                 (RF-95, TC-M07-G001)
#   .\correr_m07.ps1 -Caso G044                 (RF-101: lo detecta por la carpeta)
#   .\correr_m07.ps1 -Caso G003 -Ttl            (incluye el caso del TTL de 5 minutos, tarda ~6 min)
#   .\correr_m07.ps1 -Caso G042 -CorreoAdmin admin.dev@gmail.com   (si el administrador con permisos es otro)
#
# Igual que correr_newman.ps1: NO guarda nada en disco ni en el registro de Windows. Pide solo las
# variables que la coleccion usa; los secretos se escriben ocultos y viven unicamente en esta terminal
# (variables QA_*). Al cerrarla, desaparecen. Si ya las definiste en la terminal, no vuelve a pedirlas.
#
# Variables que puede pedir:
#   sandbox_secret        X-Sandbox-Secret del ambiente TEST
#   contrasena_admin      contrasena de admin.rol@gmail.com
#   contrasena_contador   contrasena de contador@gmail.com (los usuarios qa.m07.* usan la misma)
#   secret_aaef / secret_m2m / secret_ip / secret_vencido / secret_susp / secret_rev
#                         client_secret de los clientes QA_M07_* (los entrega el DBA por privado)
param(
  [Parameter(Mandatory=$true)][string]$Caso,
  [string]$Rf = '',
  [string]$BaseUrl = 'https://api.inmero.co/api-sgpmp-test',
  [string]$CorreoAdmin = '',
  [switch]$Ttl
)

$id = "TC-M07-$Caso"
if (-not $Rf) {
  $hallado = Get-ChildItem -Path $PSScriptRoot -Directory -Filter 'RF-*' | ForEach-Object { Join-Path $_.FullName $id } | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $hallado) { Write-Host "No existe la carpeta $id en RF-95 ni RF-101" -ForegroundColor Red; exit 1 }
  $Ruta = $hallado
} else { $Ruta = Join-Path $PSScriptRoot "$Rf\$id" }
$col = Join-Path $Ruta ("tc-m07-" + $Caso.ToLower() + ".json")
if (-not (Test-Path $col)) { Write-Host "No existe $col" -ForegroundColor Red; exit 1 }

$secretos = 'sandbox_secret','contrasena_admin','contrasena_contador','secret_aaef','secret_m2m','secret_ip','secret_vencido','secret_susp','secret_rev'
$texto = Get-Content $col -Raw
$args2 = @('--env-var', "base_url=$BaseUrl")
foreach ($k in $secretos) {
  $e = [regex]::Escape($k)
  # la coleccion usa la variable como {{nombre}} o dentro de un script como 'nombre' / "nombre"
  if ($texto -notmatch "(\{\{$e\}\}|['\\""]$e['\\""])") { continue }
  $envName = "QA_$($k.ToUpper())"
  $v = [Environment]::GetEnvironmentVariable($envName, 'Process')
  if (-not $v) {
    $sec = Read-Host "$k" -AsSecureString
    $v = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    [Environment]::SetEnvironmentVariable($envName, $v, 'Process')
  }
  if (-not $v) { Write-Host "Falta $k" -ForegroundColor Red; exit 1 }
  $args2 += '--env-var'; $args2 += "$k=$v"
}
if ($Ttl) { $args2 += '--env-var'; $args2 += 'ejecutar_ttl=true' }
if ($CorreoAdmin) { $args2 += '--env-var'; $args2 += "correo_admin=$CorreoAdmin" }   # si el administrador con permisos no es admin.rol@gmail.com

$res = Join-Path $Ruta 'Resultados'
New-Item -ItemType Directory -Force -Path $res | Out-Null
$html = Join-Path $res "resultado_$id.html"

$backend = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$newman = Join-Path $backend 'node_modules\.bin\newman.cmd'
if (-not (Test-Path $newman)) { $newman = 'newman' }

# El run del sandbox lo define el script (no la coleccion) para poder cerrarlo SIEMPRE: aunque Newman falle,
# se corte con Ctrl+C o la coleccion no llegue a su ultima peticion (pedido del DBA: toda corrida termina en rollback).
$runIds = @([guid]::NewGuid().ToString(), [guid]::NewGuid().ToString())
$usaSandbox = $texto -match [regex]::Escape('{{sandbox_secret}}')
if ($usaSandbox) { $args2 += '--env-var'; $args2 += "run_id=$($runIds[0])"; $args2 += '--env-var'; $args2 += "run_id_b=$($runIds[1])" }

Push-Location $Ruta
try {
  & $newman run $col -r 'cli,htmlextra' --reporter-htmlextra-export $html --reporter-htmlextra-title $id --timeout-request 120000 --timeout-script 900000 --disable-unicode @args2
  $rc = $LASTEXITCODE
} finally {
  Pop-Location
  if ($usaSandbox) {
    foreach ($runId in $runIds) {
      try {
        Invoke-WebRequest -Method Delete -Uri "$BaseUrl/test-control/runs/$runId" -Headers @{ 'X-Sandbox-Secret' = [Environment]::GetEnvironmentVariable('QA_SANDBOX_SECRET', 'Process') } -UseBasicParsing -TimeoutSec 30 | Out-Null
        Write-Host "Run $runId cerrado con rollback." -ForegroundColor DarkGray
      } catch {
        # 404 = la coleccion ya lo habia cerrado (o nunca lo abrio): es lo normal. Otro error: avisar al DBA con este run_id.
        if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 404) { Write-Host "Run $runId ya estaba cerrado." -ForegroundColor DarkGray }
        else { Write-Host "ATENCION: no pude cerrar el run $runId. Avisale a Samuel para liberar la sesion." -ForegroundColor Red }
      }
    }
  }
}

if (Test-Path $html) {
  python (Join-Path $PSScriptRoot 'redactar_m07.py') $html
  if ($LASTEXITCODE -ne 0) { Write-Host 'ATENCION: el reporte aun puede traer secretos; NO lo subas a Git.' -ForegroundColor Red }
}
Write-Host "Reporte: $html" -ForegroundColor Cyan
exit $rc
