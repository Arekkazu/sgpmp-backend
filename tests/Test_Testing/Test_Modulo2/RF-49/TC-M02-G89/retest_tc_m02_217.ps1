# ==================================================================
# Script de ejecución / re-test: TC-M02-217 (RF-49)
# Validación de superación automática (ACTIVA -> SUPERADA) vía POST
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando re-test TC-M02-217 (Superación Automática)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$collection = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/test_tc_m02_g89.json"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/RESULTADOS/reporte_TC-M02-217.html"

npx newman run $collection `
  --folder "TC-M02-217" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportPath `
  --reporter-htmlextra-title "Reporte TC-M02-217 - Superacion Automatica"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] TC-M02-217 supero todas las aserciones (Superación automática verificada)." -ForegroundColor Green
} else {
    Write-Host "`n[FALLO] TC-M02-217 fallo en una o mas aserciones." -ForegroundColor Red
}

exit $exitCode
