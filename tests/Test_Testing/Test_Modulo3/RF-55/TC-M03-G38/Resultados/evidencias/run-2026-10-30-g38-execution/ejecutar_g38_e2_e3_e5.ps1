# E2, E3, E5 consecutivos: un POST cada uno al broker TEST.
# Por defecto solo comprueba. -Enviar exige MQTT_BROKER_TOKEN por Get-Credential.
# Nunca usa BROKER_SERVICE_TOKEN. No ejecuta E6.
param(
    [switch]$Enviar
)

$ErrorActionPreference = "Stop"
$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Aqui

if ($env:BROKER_SERVICE_TOKEN) {
    Write-Output "RECHAZO: BROKER_SERVICE_TOKEN esta definido; no se usa como MQTT_BROKER_TOKEN."
    exit 4
}

Write-Output "MQTT_BROKER_TOKEN_ENV=$(if ($env:MQTT_BROKER_TOKEN) { 'SET' } else { 'UNSET' })"

foreach ($esc in @("e2", "e3", "e5")) {
    python -u "$Aqui\_comando_umbral.py" comprobar $esc
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not $Enviar) {
    Write-Output "Sin -Enviar: 0 POST. Falta Bearer TEST autorizado y monitor vivo."
    exit 0
}

if (-not $env:MQTT_BROKER_TOKEN) {
    Write-Output "STOP: MQTT_BROKER_TOKEN no esta autorizado/disponible en este proceso. No se abre POST ni se sustituye por otro token."
    exit 11
}

Write-Output "STOP: -Enviar no se completa aqui sin verificacion humana de que el Bearer es TEST. No hay POST automatico."
exit 12
