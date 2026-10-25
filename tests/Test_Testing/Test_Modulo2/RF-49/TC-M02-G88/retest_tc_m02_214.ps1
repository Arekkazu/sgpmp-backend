# ==================================================================
# Script de ejecución / re-test: TC-M02-214 (RF-49)
# Validación de exclusividad de sensor POBLACIONAL (HTTP 409 esperado)
# NOTA DE CONFORMIDAD: El RF-49 Restricción 4 exige textualmente HTTP 409 Conflict.
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando re-test TC-M02-214 (Exclusividad Sensor Poblacional)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$collection = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G88/test_tc_m02_g88.json"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G88/RESULTADOS/reporte_TC-M02-214.html"

npx newman run $collection `
  --folder "TC-M02-214" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportPath `
  --reporter-htmlextra-title "Reporte TC-M02-214 - Exclusividad Sensor Poblacional"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] TC-M02-214 supero todas las aserciones (HTTP 409 verificado)." -ForegroundColor Green
} else {
    Write-Host "`n[NO CONFORME] TC-M02-214 no retorno HTTP 409 (Defecto INC-M02-G88-02 persiste)." -ForegroundColor Yellow
}

exit $exitCode
