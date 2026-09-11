# ==================================================================
# Script de ejecución / re-test: TC-M02-213 (RF-49)
# Validación de rechazo ante activo biológico inexistente (HTTP 422 esperado)
# NOTA DE CONFORMIDAD: El RF-49 exige textualmente HTTP 422 Unprocessable Entity.
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando re-test TC-M02-213 (Activo Inexistente 99999)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$collection = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G88/test_tc_m02_g88.json"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G88/RESULTADOS/reporte_TC-M02-213.html"

npx newman run $collection `
  --folder "TC-M02-213" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportPath `
  --reporter-htmlextra-title "Reporte TC-M02-213 - Activo Inexistente"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] TC-M02-213 supero todas las aserciones (HTTP 422 verificado)." -ForegroundColor Green
} else {
    Write-Host "`n[NO CONFORME] TC-M02-213 no retorno HTTP 422 (Defecto INC-M02-G88-01 persiste)." -ForegroundColor Yellow
}

exit $exitCode
