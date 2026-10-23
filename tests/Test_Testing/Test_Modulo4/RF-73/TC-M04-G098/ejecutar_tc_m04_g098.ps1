param(
    [string]$baseUrl = "https://api.inmero.co/back-sigab-test"
)

$ErrorActionPreference = "Stop"
$TC_ID = "TC-M04-G098"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptK6 = Join-Path $ScriptDir "test_tc_m04_g098.js"
$ResultadosDir = Join-Path $ScriptDir "resultados"
$JsonExport = Join-Path $ResultadosDir "resultado_${TC_ID}.json"

if (-not (Test-Path $ResultadosDir)) {
    New-Item -ItemType Directory -Path $ResultadosDir -Force | Out-Null
}

$SandboxSecret = if ($env:TEST_SANDBOX_SECRET) { $env:TEST_SANDBOX_SECRET } else { "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff" }
$AdminPassword = if ($env:TEST_ADMIN_PASSWORD) { $env:TEST_ADMIN_PASSWORD } else { "Test1234!" }

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Ejecutando Suite k6: $TC_ID (RF-73 Disponibilidad/Escala)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

k6 run `
    -e BASE_URL="$baseUrl" `
    -e TEST_SANDBOX_SECRET="$SandboxSecret" `
    -e TEST_ADMIN_PASSWORD="$AdminPassword" `
    --summary-export="$JsonExport" `
    $ScriptK6

exit $LASTEXITCODE
