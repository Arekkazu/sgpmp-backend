param(
    [string]$EngineerPassword = ""
)

$ErrorActionPreference = "Stop"

$Collection = Join-Path $PSScriptRoot "tc_m02_g15.json"
$Resultados = Join-Path $PSScriptRoot "Resultados"

New-Item -ItemType Directory -Force -Path $Resultados | Out-Null

$Html = Join-Path $Resultados "TC-M02-G15-Newman.html"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " TC-M02-G15 - RF-33 / RF-34" -ForegroundColor Cyan
Write-Host " BOLA (TC-M02-027) + mass assignment (TC-M02-028) + exposicion financiera (TC-M02-031)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

if ([string]::IsNullOrWhiteSpace($EngineerPassword)) {
    Write-Host "AVISO: no se paso -EngineerPassword. El login de Ingeniero de Campo (TC-M02-031)" -ForegroundColor Yellow
    Write-Host "fallara con 401 y ese sub-caso quedara sin verificar; el resto (027, 028) corre igual." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "Coleccion: $Collection"
Write-Host "Resultados: $Resultados"
Write-Host ""

Write-Host "Ejecutando Newman..." -ForegroundColor Yellow
Write-Host ""

newman run $Collection `
    --env-var "engineer_password=$EngineerPassword" `
    --reporters "cli,htmlextra" `
    --reporter-htmlextra-export $Html `
    --color off

$ExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan

if ($ExitCode -eq 0) {
    Write-Host " TC-M02-G15 FINALIZADO SIN ASSERTIONS FALLIDAS" -ForegroundColor Green
}
else {
    Write-Host " TC-M02-G15 PRESENTA ASSERTIONS FALLIDAS" -ForegroundColor Red
}

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "HTML: $Html"
Write-Host ""

exit $ExitCode
