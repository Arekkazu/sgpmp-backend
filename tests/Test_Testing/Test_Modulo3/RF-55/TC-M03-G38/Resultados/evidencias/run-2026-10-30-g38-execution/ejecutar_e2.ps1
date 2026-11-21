# Un POST E2 al broker TEST. No buscar tokens en disco.
# Por defecto NO envia. -Enviar pide la credencial renovada en cuadro Windows.
param(
    [switch]$Enviar
)

$ErrorActionPreference = "Stop"
$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Aqui

if (-not $Enviar) {
    python -u "$Aqui\_e2_post.py" comprobar
    Write-Output "Sin -Enviar: no hay POST ni cuadro de credencial."
    exit 0
}

$cred = Get-Credential -UserName "MQTT_BROKER_TOKEN" -Message "Bearer renovado del broker TEST (no se guarda ni se imprime)"
if (-not $cred) {
    Write-Output "CANCELADO"
    exit 3
}
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($cred.Password)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
try {
    $plain | python -u "$Aqui\_e2_post.py" enviar
    $code = $LASTEXITCODE
} finally {
    $plain = $null
}
exit $code
