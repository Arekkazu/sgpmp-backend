# ==================================================================
# Script de ejecución / re-test: TC-M02-219 (RF-49)
# Validación de rechazo de transición inválida (INACTIVA -> SUPERADA) vía PATCH
# NOTA: Congelado hasta que desarrollo implemente el endpoint PATCH.
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando re-test TC-M02-219 (Transición Inválida PATCH)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$collection = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/test_tc_m02_g89.json"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/RESULTADOS/reporte_TC-M02-219.html"

npx newman run $collection `
  --folder "TC-M02-219" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportPath `
  --reporter-htmlextra-title "Reporte TC-M02-219 - Transicion Invalida"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] TC-M02-219 supero todas las aserciones (HTTP 409 verificado)." -ForegroundColor Green
} else {
    Write-Host "`n[NO CONFORME] TC-M02-219 fallo (Defecto INC-M02-G89-01 persiste - Endpoint no implementado)." -ForegroundColor Yellow
}

exit $exitCode
