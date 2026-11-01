# TC-M03-101 laboratorio sintético. Credenciales solo Get-Credential -> stdin.
# No persiste secretos. No usa BROKER_SERVICE_TOKEN.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $here "ejecutar_tc101.py"

if ($env:BROKER_SERVICE_TOKEN) {
    Write-Output "RECHAZO: BROKER_SERVICE_TOKEN definido; no se usa."
    exit 4
}

$ssh = Get-Credential -UserName sgpmp -Message "SSH sgpmp RASPBERRY3B (TC-M03-101, sin restart)"
if (-not $ssh) { Write-Output "SSH_CANCELLED"; exit 3 }
$mqtt = Get-Credential -Message "MQTT SUB TEST (usuario/clave broker, solo lectura de topics)"
if (-not $mqtt) { Write-Output "MQTT_CANCELLED"; exit 3 }
$tok = Get-Credential -UserName Bearer -Message "MQTT_BROKER_TOKEN TEST para POST /v1/commands"
if (-not $tok) { Write-Output "TOKEN_CANCELLED"; exit 3 }

function Get-Plain([System.Security.SecureString]$sec) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) | Out-Null }
}

$sshP = Get-Plain $ssh.Password
$mqttP = Get-Plain $mqtt.Password
$tokP = Get-Plain $tok.Password
$mqttU = $mqtt.UserName

try {
    ($sshP + "`n" + $mqttU + "`n" + $mqttP + "`n" + $tokP + "`n") | python -u $py
    $code = $LASTEXITCODE
} finally {
    $sshP = $null; $mqttP = $null; $tokP = $null
    $ssh = $null; $mqtt = $null; $tok = $null
}
exit $code
