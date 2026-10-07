# TC-M09-G63-02 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA (400 x2)

### G63-02 — Campo `punto_instalacion`
- **Tipo:** Valores límite · **Ejecutable:** Sí.
- **Casos verificados:** vacío → 400; 101 → 400. **Pendiente:** 99 / 100 → 201 (requiere sensor y área reales).
- **Verificar** que el rechazo venga de la validación de aplicación (lo ocurrido: sí, `VAL_ENTRADA` con mensaje del campo), no de un truncamiento en BD.
