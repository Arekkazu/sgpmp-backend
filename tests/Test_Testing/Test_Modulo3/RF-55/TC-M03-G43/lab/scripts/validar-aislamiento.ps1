# Validación de URLs del lab G43. No arranca servicios. No imprime secretos.
$ErrorActionPreference = "Stop"
$lab = Split-Path $PSScriptRoot -Parent
$envFile = Join-Path $lab ".env.g43"
if (-not (Test-Path $envFile)) {
    Write-Output "FALTA .env.g43 (copiar desde .env.g43.example). No se leen secretos de otros .env."
    exit 2
}
$vals = @{}
Get-Content -LiteralPath $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $k, $v = $_.Split('=', 2)
    $vals[$k.Trim()] = $v.Trim()
}

function Assert-DbName([string]$url, [string]$label) {
    if ([string]::IsNullOrWhiteSpace($url)) {
        Write-Output "FAIL $label vacia"
        return $false
    }
    $name = ($url -split '/')[-1]
    if ($name -eq "sgpmp" -or $name -eq "sgpmp_pr14_test") {
        Write-Output "FAIL $label apunta a base prohibida (nombre detectado, URL no impresa)"
        return $false
    }
    if ($name -ne "sgpmp_g43_test") {
        Write-Output "FAIL $label no es sgpmp_g43_test"
        return $false
    }
    if ($url -notmatch '127\.0\.0\.1:5439' -and $url -notmatch 'localhost:5439') {
        Write-Output "FAIL $label no usa 127.0.0.1:5439"
        return $false
    }
    Write-Output "OK $label nombre=sgpmp_g43_test host_local_5439"
    return $true
}

$ok = $true
$ok = (Assert-DbName $vals["DATABASE_URL"] "DATABASE_URL") -and $ok
if ($vals["POSTGRES_DB"] -ne "sgpmp_g43_test") {
    Write-Output "FAIL POSTGRES_DB distinto de sgpmp_g43_test"
    $ok = $false
} else { Write-Output "OK POSTGRES_DB" }
if ($vals["G43_PG_HOST_PORT"] -in @("5433", "5447", "5448")) {
    Write-Output "FAIL puerto PG colisiona con infra existente"
    $ok = $false
}
if ($vals["MQTT_HOST"] -ne "127.0.0.1" -and $vals["MQTT_HOST"] -ne "localhost") {
    Write-Output "FAIL MQTT_HOST no es loopback"
    $ok = $false
} else { Write-Output "OK MQTT_HOST loopback" }
if ($vals["MQTT_PORT"] -ne "1884" -and $vals["G43_MQTT_HOST_PORT"] -ne "1884") {
    Write-Output "WARN puerto MQTT distinto de 1884"
}
if ($vals["BACKEND_URL"] -notmatch '127\.0\.0\.1:18043' -and $vals["BACKEND_URL"] -notmatch 'localhost:18043') {
    Write-Output "FAIL BACKEND_URL no es API local G43"
    $ok = $false
} else { Write-Output "OK BACKEND_URL local" }
if ($vals["EDGE_SERIALS"] -match 'RASPBERRY|G38|G41') {
    Write-Output "FAIL serial de lab reutiliza Raspberry/G38/G41"
    $ok = $false
} else { Write-Output "OK EDGE_SERIALS lab" }

if ($ok) { Write-Output "CHECKLIST_AISLAMIENTO=OK (estatico; servicios no arrancados)"; exit 0 }
Write-Output "CHECKLIST_AISLAMIENTO=FAIL"; exit 1
