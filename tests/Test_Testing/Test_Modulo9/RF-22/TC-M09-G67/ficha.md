# TC-M09-G67 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-09, reintento1):** APROBADO (2/2) — rollback confirmado: sensor sigue en A, no existe asociación en B.

### G67-02 — Rollback de asociación y reasignación
- **Tipo:** Atomicidad · **Ejecutable:** con inyección de fallo (mocks). **Confirmado: se cumple**, pero por una red de seguridad genérica (`get_db()`, `src/shared/database.py`), no por un `try/except` dedicado en el use case.
- **Hallazgo (no es un bug, es una mejora pendiente):** en `AsociarSensorAreaUseCase.execute()`, el bloque que cierra la asociación anterior (reasignación: `terminar()` + `actualizar()` + `auditoria_repo.registrar(tipo_operacion="UPDATE")`) está **fuera** del `try/except` que envuelve la asociación nueva — ese `try/except` solo cubre el `CREATE` + commit. Si el `auditoria_repo.registrar()` del `UPDATE` falla, no hay ningún `except` local; sube sin capturar y se salva solo porque `sensor_area_repo.actualizar()` usa `db.flush()` (no commit) y la red de seguridad de `get_db()` hace rollback de todo el request. Funciona hoy, pero es manejo implícito, no explícito — vale la pena un issue menor de mejora (no de corrección urgente).

## Reintento1 (2026-10-09)
- Script: `test_tc_m09_g67_rollback_reasignacion.py` (pytest, mocks — sin BD real)
- Reporte: `resultados/resultado_TC-M09-G67_reintento1.html`
- 2/2 passed: a nivel use case directo y a nivel endpoint (reproduciendo fielmente la red de seguridad real de `get_db()`). En ambos: 0 commits, 1 rollback, 0 asociaciones creadas en B.
