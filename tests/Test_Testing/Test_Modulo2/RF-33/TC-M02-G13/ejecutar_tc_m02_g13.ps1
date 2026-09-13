$ErrorActionPreference = "Stop"

$Collection = Join-Path $PSScriptRoot "tc_m02_g13.json"
$Resultados = Join-Path $PSScriptRoot "Resultados"

New-Item -ItemType Directory -Force -Path $Resultados | Out-Null

$Html = Join-Path $Resultados "TC-M02-G13-Newman.html"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " TC-M02-G13 - RF-33" -ForegroundColor Cyan
Write-Host " Inmutabilidad de campos controlados" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Coleccion: $Collection"
Write-Host "Resultados: $Resultados"
Write-Host ""

Write-Host "Ejecutando Newman..." -ForegroundColor Yellow
Write-Host ""

newman run $Collection `
    --reporters "cli,htmlextra" `
    --reporter-htmlextra-export $Html `
    --color off

$ExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan

if ($ExitCode -eq 0) {
    Write-Host " TC-M02-G13 FINALIZADO SIN ASSERTIONS FALLIDAS" -ForegroundColor Green
}
else {
    Write-Host " TC-M02-G13 PRESENTA ASSERTIONS FALLIDAS" -ForegroundColor Red
}

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "HTML: $Html"
Write-Host ""

exit $ExitCode