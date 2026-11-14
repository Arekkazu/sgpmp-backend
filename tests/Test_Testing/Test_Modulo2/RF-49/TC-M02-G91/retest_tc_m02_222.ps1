# Retest individual para TC-M02-222 (Rechazar DELETE)
Write-Host "Ejecutando retest para TC-M02-222..." -ForegroundColor Cyan

npx newman run tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G91/test_tc_m02_g91.json `
  --folder "TC-M02-222" `
  -r cli,htmlextra `
  --reporter-htmlextra-export tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G91/RESULTADOS/reporte_TC-M02-222.html `
  --reporter-htmlextra-title "Reporte TC-M02-222 - Rechazar DELETE"

$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    Write-Host "[EXITO] TC-M02-222 supero todas las aserciones." -ForegroundColor Green
} else {
    Write-Host "[FALLO] TC-M02-222 fallo." -ForegroundColor Red
}
exit $exitCode
