# ==================================================================
# Script de ejecución / re-test: TC-M02-221 (RF-49)
# Validación de coherencia territorial de infraestructura (Misma Finca)
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando re-test TC-M02-221 (Coherencia de Infraestructura)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$collection = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G90/test_tc_m02_g90.json"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G90/RESULTADOS/reporte_TC-M02-221.html"

npx newman run $collection `
  --folder "TC-M02-221" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportPath `
  --reporter-htmlextra-title "Reporte TC-M02-221 - Coherencia Infraestructura"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] TC-M02-221 supero la aserción de oráculo abierto (Respuesta analizada)." -ForegroundColor Green
} else {
    Write-Host "`n[FALLO] TC-M02-221 fallo en la aserción esperada." -ForegroundColor Red
}

exit $exitCode
