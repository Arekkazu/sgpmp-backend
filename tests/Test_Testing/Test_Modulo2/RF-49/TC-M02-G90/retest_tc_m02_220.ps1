# ==================================================================
# Script de ejecución / re-test: TC-M02-220 (RF-49)
# Validación de asociación tipo AMBIENTAL en endpoint de activos
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando re-test TC-M02-220 (Asociación AMBIENTAL)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$collection = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G90/test_tc_m02_g90.json"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G90/RESULTADOS/reporte_TC-M02-220.html"

npx newman run $collection `
  --folder "TC-M02-220" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportPath `
  --reporter-htmlextra-title "Reporte TC-M02-220 - Asociacion AMBIENTAL"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] TC-M02-220 supero todas las aserciones (HTTP 201 verificado)." -ForegroundColor Green
} else {
    Write-Host "`n[FALLO] TC-M02-220 fallo en una o mas aserciones." -ForegroundColor Red
}

exit $exitCode
