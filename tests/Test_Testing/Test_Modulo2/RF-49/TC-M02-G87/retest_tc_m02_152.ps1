# ==================================================================
# Script de ejecución / re-test: TC-M02-152 (RF-49)
# Validación de control de acceso BOLA (OWASP API1) y defecto RBAC del Productor
# Estrategia: Exclusivamente Pytest de integración contra API REST TEST.
# NOTA DE SEGURIDAD: No requiere ni realiza modificaciones estructurales a la BD TEST
#                    (sin triggers, sin funciones, sin DDL, sin permisos DBA).
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando prueba TC-M02-152 (BOLA y Autorizacion RBAC via Pytest)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$testFile = "tests/integration/test_rf49_bola_sensor_cross_finca_integration.py"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G87/RESULTADOS/reporte_TC-M02-152_pytest.html"

.venv\Scripts\pytest $testFile `
  -v `
  --html=$reportPath `
  --self-contained-html

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] Suite TC-M02-152 ejecutada con exito (3/3 escenarios validados)." -ForegroundColor Green
    Write-Host "NOTA: El Escenario B documenta la no-conformidad de RBAC del Productor." -ForegroundColor Yellow
} else {
    Write-Host "`n[FALLA] Suite TC-M02-152 no supero las aserciones (Exit code $exitCode)." -ForegroundColor Red
}

exit $exitCode
