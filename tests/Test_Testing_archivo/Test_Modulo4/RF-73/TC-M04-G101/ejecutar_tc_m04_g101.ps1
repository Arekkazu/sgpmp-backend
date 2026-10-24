param(
    [string]$baseUrl = "https://api.inmero.co/back-sigab-test",
    [string]$baseUrlHttp = "http://api.inmero.co/back-sigab-test"
)

$ErrorActionPreference = "Stop"
$TC_ID = "TC-M04-G101"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Collection = Join-Path $ScriptDir "test_tc_m04_g101.json"
$ResultadosDir = Join-Path $ScriptDir "resultados"
$RawExport = Join-Path $ResultadosDir "_raw_newman.json"
$HtmlExport = Join-Path $ResultadosDir "resultado_${TC_ID}.html"
$ConsolidarScript = Join-Path $ScriptDir "consolidar-resultados.cjs"

if (-not (Test-Path $ResultadosDir)) {
    New-Item -ItemType Directory -Path $ResultadosDir -Force | Out-Null
}

$SandboxSecret = if ($env:TEST_SANDBOX_SECRET) { $env:TEST_SANDBOX_SECRET } else { "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff" }
$AdminPassword = if ($env:TEST_ADMIN_PASSWORD) { $env:TEST_ADMIN_PASSWORD } else { "Test1234!" }

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Ejecutando Suite Newman: $TC_ID (RF-73 TLS / ASVS V9)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

npx newman run $Collection `
    --env-var baseUrl="$baseUrl" `
    --env-var baseUrlHttp="$baseUrlHttp" `
    --env-var TEST_SANDBOX_SECRET="$SandboxSecret" `
    --env-var TEST_ADMIN_PASSWORD="$AdminPassword" `
    -r cli,json,htmlextra `
    --reporter-json-export $RawExport `
    --reporter-htmlextra-export $HtmlExport

$newmanExit = $LASTEXITCODE

if (Test-Path $ConsolidarScript) {
    node $ConsolidarScript
}

# ── FASE SEPARADA (G101): descomentar cuando se ejecute testssl.sh en entorno con el binario instalado ──
# testssl.sh --severity HIGH --protocols --cipher-per-proto `
#   https://api.inmero.co/back-sigab-test/ | Out-File -Encoding utf8 `
#   (Join-Path $ScriptDir "evidencias\testssl_output.txt")

exit $newmanExit
