# ==================================================================
# Script de re-ejecución diferida: TC-M02-150
# Caso de Prueba: TC-M02-G84 (RF-49 · CU11)
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando Re-test diferido de TC-M02-150 (RF-49)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$collectionPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/test_tc_m02_g84.json"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/resultados/resultado_TC-M02-G84_reintento3.html"

$adminEmail = if ($env:TEST_ADMIN_EMAIL) { $env:TEST_ADMIN_EMAIL } else { "administador.dev@gmail.com" }
$adminPassword = if ($env:TEST_ADMIN_PASSWORD) { $env:TEST_ADMIN_PASSWORD } else { "" }

npx newman run $collectionPath `
  --folder "TC-M02-150" `
  --env-var "admin_email=$adminEmail" `
  --env-var "admin_password=$adminPassword" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportPath `
  --reporter-htmlextra-title "Reporte Re-test TC-M02-G84 Reintento 3 - TC-M02-150"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] El subcaso TC-M02-150 paso con 100% de aserciones exitosas." -ForegroundColor Green
    Write-Host "[INFO] Reporte generado en: $reportPath" -ForegroundColor Green
} else {
    Write-Host "`n[INFO] El subcaso TC-M02-150 no supero todas las aserciones (Exit code $exitCode)." -ForegroundColor Yellow
}

exit $exitCode
