# ==================================================================
# Script de ejecución / re-test: TC-M02-218 (RF-49)
# Validación de reactivación (INACTIVA -> ACTIVA) vía PATCH
# NOTA: Congelado hasta que desarrollo implemente el endpoint PATCH.
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando re-test TC-M02-218 (Reactivación PATCH)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$collection = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/test_tc_m02_g89.json"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/RESULTADOS/reporte_TC-M02-218.html"

npx newman run $collection `
  --folder "TC-M02-218" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportPath `
  --reporter-htmlextra-title "Reporte TC-M02-218 - Reactivacion"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] TC-M02-218 supero todas las aserciones (HTTP 200 verificado)." -ForegroundColor Green
} else {
    Write-Host "`n[NO CONFORME] TC-M02-218 fallo (Defecto INC-M02-G89-01 persiste - Endpoint no implementado)." -ForegroundColor Yellow
}

exit $exitCode
