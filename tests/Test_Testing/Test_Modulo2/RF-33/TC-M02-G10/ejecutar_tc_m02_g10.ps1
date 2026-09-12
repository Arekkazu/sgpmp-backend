# ============================================
# EJECUCION TC-M02-G10 - RF-33
# Newman + reporte HTML
# ============================================

$ErrorActionPreference = "Stop"

$TestDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$Collection = Join-Path $TestDir "tc_m02_g10.json"

$ResultsDir = Join-Path $TestDir "Resultados"

$Report = Join-Path $ResultsDir "TC-M02-G10-Newman.html"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   EJECUCION TC-M02-G10 - RF-33" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $Collection)) {
    Write-Host "ERROR: No se encontro la coleccion:" -ForegroundColor Red
    Write-Host $Collection -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $ResultsDir)) {
    New-Item -ItemType Directory -Path $ResultsDir | Out-Null
}

if (Test-Path $Report) {
    Remove-Item $Report -Force
    Write-Host "Reporte anterior eliminado." -ForegroundColor DarkGray
}

Write-Host "Coleccion:" -ForegroundColor Gray
Write-Host $Collection -ForegroundColor White

Write-Host ""
Write-Host "Reporte:" -ForegroundColor Gray
Write-Host $Report -ForegroundColor White

Write-Host ""
Write-Host "Ejecutando Newman..." -ForegroundColor Yellow
Write-Host ""

newman run "$Collection" `
    --reporters "cli,htmlextra" `
    --reporter-htmlextra-export "$Report"

$ExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan

if ($ExitCode -eq 0) {
    Write-Host "   PRUEBA FINALIZADA CORRECTAMENTE" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Reporte HTML generado en:" -ForegroundColor Green
    Write-Host $Report -ForegroundColor White
} else {
    Write-Host "   LA PRUEBA PRESENTO ERRORES" -ForegroundColor Red
    Write-Host "============================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Codigo de salida Newman: $ExitCode" -ForegroundColor Red

    if (Test-Path $Report) {
        Write-Host ""
        Write-Host "El reporte HTML fue generado en:" -ForegroundColor Yellow
        Write-Host $Report -ForegroundColor White
    }
}

Write-Host ""