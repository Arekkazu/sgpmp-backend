# Eliminaciones / reubicaciones del cierre documental G96 (2026-11-13)

## Eliminados
1. resultados/ejecucion_A_B/pytest_integracion_sin_url.log
   - Motivo: log provisional del bloqueo B sin TEST_DATABASE_URL; sustituido por diagnostico_integral y resultado_integracion.
2. resultados/ejecucion_A_B/ (carpeta)
   - Motivo: vaciada tras reubicar evidencias a evidencias/*; carpeta vacía eliminada.
3. __pycache__/ dentro de TC-M06-G96
   - Motivo: bytecode local sin valor probatorio.

## Reubicados (conservados)
1. Evidencias A/B -> resultados/evidencias/{dominio,integracion,criterios}/
2. _capturar_evidencia_alerta.py -> herramientas/ (script auxiliar, no evidencia primaria)
3. Histórico primera evaluación -> resultados/historico/primera_evaluacion/ (restaurado desde git HEAD)

## No eliminados
- Casos fuente (ficha, json, tests, ejecutar_*)
- JSON de evidencia, HTML pytest, alembic log, preparación, matriz, diagnóstico
