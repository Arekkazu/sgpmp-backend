# ==================================================================
# Script de re-ejecución diferida: TC-M02-150
# Estado actual: BLOQUEADO hasta que el Módulo 3 (Telemetría)
# esté implementado y disponible en TEST.
# Motivo del bloqueo: el subcaso requiere verificar el estado de
# heartbeat del dispositivo IoT, servicio que provee M03.
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando Re-test diferido de TC-M02-150 (RF-49)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$collectionPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/test_tc_m02_g84.json"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/RESULTADOS/reporte_TC-M02-150.html"

npx newman run $collectionPath `
  --folder "TC-M02-150" `
  -r cli,htmlextra `
  --reporter-htmlextra-export $reportPath `
  --reporter-htmlextra-title "Reporte Re-test TC-M02-150 - Advertencia Dispositivo Desconectado"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] El subcaso TC-M02-150 paso con 100% de aserciones exitosas." -ForegroundColor Green
    Write-Host "[INFO] El caso agrupado TC-M02-G84 puede ser cerrado como PASS COMPLETO." -ForegroundColor Green
} else {
    Write-Host "`n[INFO] El subcaso TC-M02-150 no supero todas las aserciones (Exit code $exitCode)." -ForegroundColor Yellow
    Write-Host "[INFO] Verificar la disponibilidad y despliegue del Modulo 3 (Telemetria) en TEST." -ForegroundColor Yellow
}

exit $exitCode
