# ==================================================================
# Script de ejecución / re-test: TC-M02-216 (RF-49)
# Validación de desactivación manual (ACTIVA -> INACTIVA) vía PATCH
# ADVERTENCIA: Depende de id_asociacion_B generada previamente por TC-M02-217.
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando re-test TC-M02-216 (Desactivación Manual PATCH)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$collection = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/test_tc_m02_g89.json"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/resultados/resultado_TC-M02-G89_216_aislado.html"

$adminEmail = if ($env:TEST_ADMIN_EMAIL) { $env:TEST_ADMIN_EMAIL } else { "administador.dev@gmail.com" }
$adminPassword = if ($env:TEST_ADMIN_PASSWORD) { $env:TEST_ADMIN_PASSWORD } else { "" }
$idAsocB = if ($env:ID_ASOCIACION_B) { $env:ID_ASOCIACION_B } else { "" }

if (-not $idAsocB) {
    Write-Warning "[ADVERTENCIA] TC-M02-216 depende de id_asociacion_B generada por TC-M02-217."
    Write-Warning "Defina `$env:ID_ASOCIACION_B antes de ejecutar este script aislado, o ejecute la coleccion completa."
}

npx newman run $collection `
  --folder "TC-M02-216" `
  --env-var "admin_email=$adminEmail" `
  --env-var "admin_password=$adminPassword" `
  --env-var "id_asociacion_B=$idAsocB" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportPath `
  --reporter-htmlextra-title "Reporte TC-M02-216 - Desactivacion Aislado"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] TC-M02-216 supero todas las aserciones (HTTP 200 verificado)." -ForegroundColor Green
} else {
    Write-Host "`n[FALLO] TC-M02-216 fallo en una o mas aserciones." -ForegroundColor Yellow
}

exit $exitCode
