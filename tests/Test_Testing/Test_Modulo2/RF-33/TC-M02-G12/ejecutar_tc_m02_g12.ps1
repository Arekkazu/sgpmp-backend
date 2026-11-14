$ErrorActionPreference = "Stop"

$Collection = Join-Path $PSScriptRoot "tc_m02_g12.json"
$Resultados = Join-Path $PSScriptRoot "Resultados"
$Report = Join-Path $Resultados "TC-M02-G12-Newman.html"

if (!(Test-Path $Resultados)) {
    New-Item -ItemType Directory -Force $Resultados | Out-Null
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " TC-M02-G12 - RF-33 / RF-16" -ForegroundColor Cyan
Write-Host " Validacion de atributos dinamicos" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Coleccion:" -ForegroundColor Yellow
Write-Host $Collection

Write-Host ""
Write-Host "Reporte:" -ForegroundColor Yellow
Write-Host $Report

Write-Host ""
Write-Host "Ejecutando Newman..." -ForegroundColor Green
Write-Host ""

newman run "$Collection" `
    --reporters "cli,htmlextra" `
    --reporter-htmlextra-export "$Report"

$exitCode = $LASTEXITCODE

Write-Host ""

if ($exitCode -eq 0) {
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host " Newman finalizo sin fallos de aserciones." -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Reporte generado:" -ForegroundColor Cyan
    Write-Host $Report
}
else {
    Write-Host "==============================================" -ForegroundColor Red
    Write-Host " Newman finalizo con errores." -ForegroundColor Red
    Write-Host "==============================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Revisar reporte:" -ForegroundColor Yellow
    Write-Host $Report
}

exit $exitCode