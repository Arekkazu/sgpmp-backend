# Runner PowerShell para TC-M03-G185
param(
    [string]$BaseUrl = "https://api.inmero.co/back-sigab-test",
    [string]$AdminPassword = $env:TEST_ADMIN_PASSWORD,
    [string]$RolePassword = $env:TEST_ROLE_PASSWORD,
    [string]$SandboxSecret = $env:TEST_SANDBOX_SECRET
)

$ErrorActionPreference = "Stop"

if (-not $SandboxSecret) {
    Write-Warning "TEST_SANDBOX_SECRET no está definida. Usando valor por defecto del entorno TEST."
    $SandboxSecret = "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff"
}

if (-not $RolePassword) {
    $RolePassword = "Test1234!"
}

$CurrentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CollectionPath = Join-Path $CurrentDir "test_tc_m03_g185.json"
$ResultadosDir = Join-Path $CurrentDir "resultados"
$ReportHtml = Join-Path $ResultadosDir "resultado_TC-M03-G185.html"

if (-not (Test-Path $ResultadosDir)) {
    New-Item -ItemType Directory -Path $ResultadosDir -Force | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$RunDir = Join-Path $CurrentDir "RESULTADOS/run-$Timestamp"
New-Item -ItemType Directory -Path $RunDir -Force | Out-Null

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  EJECUTANDO RUNNER TC-M03-G185 (OWASP API1 - BOLA Auditoria)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

newman run $CollectionPath `
    --env-var "baseUrl=$BaseUrl" `
    --env-var "adminPassword=$AdminPassword" `
    --env-var "rolePassword=$RolePassword" `
    --env-var "sandboxSecret=$SandboxSecret" `
    --reporters cli,htmlextra `
    --reporter-htmlextra-export $ReportHtml `
    --timeout-request 15000 `
    --delay-request 300

$NewmanExitCode = $LASTEXITCODE

Copy-Item $ReportHtml (Join-Path $RunDir "resultado_TC-M03-G185.html") -Force

Write-Host "`nConsultando estado en qa-dashboard scanner..." -ForegroundColor Yellow
$DashboardDir = Join-Path $CurrentDir "../../../qa-dashboard"
if (Test-Path $DashboardDir) {
    Push-Location $DashboardDir
    try {
        python3 -c "import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M03-G185'])"
    } catch {
        Write-Warning "No se pudo ejecutar scanner: $_"
    }
    Pop-Location
}

exit $NewmanExitCode
