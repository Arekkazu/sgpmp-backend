$ErrorActionPreference = "Stop"

$Collection = Join-Path $PSScriptRoot "tc_m02_g14.json"
$Resultados = Join-Path $PSScriptRoot "Resultados"

New-Item -ItemType Directory -Force -Path $Resultados | Out-Null

$Html = Join-Path $Resultados "TC-M02-G14-Newman.html"
$Json = Join-Path $Resultados "TC-M02-G14-Newman.json"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " TC-M02-G14 - RF-33" -ForegroundColor Cyan
Write-Host " Validacion origen financiero y costo" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Coleccion: $Collection"
Write-Host "Resultados: $Resultados"
Write-Host ""

if (-not (Test-Path $Collection)) {
    Write-Host "ERROR: No se encontro la coleccion." -ForegroundColor Red
    exit 1
}

Write-Host "Ejecutando Newman..." -ForegroundColor Yellow
Write-Host ""

newman run $Collection `
    --reporters "cli,htmlextra" `
    --reporter-htmlextra-export $Html `
    --reporter-json-export $Json `
    --color off

$ExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan

if ($ExitCode -eq 0) {
    Write-Host " TC-M02-G14 FINALIZADO SIN ASSERTIONS FALLIDAS" -ForegroundColor Green
}
else {
    Write-Host " TC-M02-G14 PRESENTA ASSERTIONS FALLIDAS" -ForegroundColor Red
}

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "HTML: $Html"
Write-Host "JSON: $Json"
Write-Host ""

exit $ExitCode