# TC-M09-G62-02 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** FALLA contra consolidado (404 vs 422, decision 7)

### G62-02 — Integridad de la asociación
- **Tipo:** Integridad · **Ejecutable:** Sí.
- **Casos verificados:** sensor inexistente → **404** (no 422). Punto vacío → 400. Punto 101 caracteres → 400.
- **Pendiente:** dispositivo inexistente → 404; sensor de otro dispositivo → 422 (verificar código real); área inexistente o inactiva → 404; duplicado vigente → 409 `ASOCIACION_DUPLICADA`.
- **Quitado:** "un sensor no puede tener más de una asociación activa" (es el 409 `REASIGNACION_REQUIERE_CONFIRMACION` de G64-02).
