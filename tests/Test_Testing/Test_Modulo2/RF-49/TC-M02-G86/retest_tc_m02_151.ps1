# ==================================================================
# Script de ejecución / re-test: TC-M02-151 (RF-49)
# Validación de reversión transaccional (rollback) ante fallo de auditoría
# Estrategia: Exclusivamente prueba Pytest con monkeypatch in-process (no Newman).
# NOTA DE SEGURIDAD: No requiere modificaciones a la BD TEST
#                    (sin triggers, sin funciones, sin DDL, sin permisos DBA).
# ==================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando prueba TC-M02-151 (Reversion de auditoria via Pytest)..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$testFile = "tests/integration/test_rf49_reversion_auditoria_integration.py"
$reportPath = "tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G86/RESULTADOS/reporte_TC-M02-151_pytest.html"

.venv\Scripts\pytest $testFile `
  -v `
  --html=$reportPath `
  --self-contained-html

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n[EXITO] Subcaso TC-M02-151 paso con 100% de verificaciones conformes (Rollback efectivo verificado)." -ForegroundColor Green
} else {
    Write-Host "`n[FALLA] Subcaso TC-M02-151 no supero las aserciones (Exit code $exitCode)." -ForegroundColor Red
}

exit $exitCode
