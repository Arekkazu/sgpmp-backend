# TC-M09-G60 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-09, reintento1):** APROBADO (4/4) — rollback completo confirmado ante fallo de auditoría.

### G60-02 — Rollback por fallo de auditoría
- **Tipo:** Atomicidad · **Ejecutable:** con inyección de fallo (mocks sobre `auditoria_repo.registrar`, mismo patrón que TC-M09-G73). **Confirmado: `RegistrarDispositivoIotUseCase.execute()` hace rollback completo** (0 commits, dispositivo nunca queda persistido) ante un fallo de auditoría.
- **Nota sobre "SENSOR y CAMARA":** el código no distingue categoría en este flujo — `execute()` es idéntico sin importar `id_tipo_dispositivo` (confirmado leyendo el código; "CAMARA" no existe como concepto en `src/configuration`, consistente con TC-M09-G130). Se parametrizó con dos `id_tipo_dispositivo` distintos para confirmarlo, no porque exista una rama de código real por categoría.

## Reintento1 (2026-10-09)
- Script: `test_tc_m09_g60_rollback_auditoria.py` (pytest, mocks — sin BD real)
- Reporte: `resultados/resultado_TC-M09-G60_reintento1.html`
- 4/4 passed (2 escenarios × 2 "categorías"): rollback a nivel use case y a nivel endpoint, en ambos casos 0 commits / 1 rollback / dispositivo nunca persistido.
