# ==================================================================
# Script de ejecución / re-test: TC-M02-216 (RF-49)
# Validación de desactivación manual (ACTIVA -> INACTIVA) vía PATCH
# NOTA: Congelado hasta que desarrollo implemente el endpoint PATCH.
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando re-test TC-M02-216 (Desactivación Manual PATCH)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$collection = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/test_tc_m02_g89.json"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/RESULTADOS/reporte_TC-M02-216.html"

npx newman run $collection `
  --folder "TC-M02-216" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportPath `
  --reporter-htmlextra-title "Reporte TC-M02-216 - Desactivacion"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] TC-M02-216 supero todas las aserciones (HTTP 200 verificado)." -ForegroundColor Green
} else {
    Write-Host "`n[NO CONFORME] TC-M02-216 fallo (Defecto INC-M02-G89-01 persiste - Endpoint no implementado)." -ForegroundColor Yellow
}

exit $exitCode
