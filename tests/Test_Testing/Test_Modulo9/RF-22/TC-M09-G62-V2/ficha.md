# TC-M09-G62-V2 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** FALLA contra consolidado (9/11): sensor inexistente 404 (matriz 422); dispositivo inexistente 422 (matriz 404)

### G62-02 — Integridad de la asociación
- **Tipo:** Integridad · **Ejecutable:** Sí.
- **Casos verificados:** sensor inexistente → **404** (no 422). Punto vacío → 400. Punto 101 caracteres → 400.
- **Pendiente:** dispositivo inexistente → 404; sensor de otro dispositivo → 422 (verificar código real); área inexistente o inactiva → 404; duplicado vigente → 409 `ASOCIACION_DUPLICADA`.
- **Quitado:** "un sensor no puede tener más de una asociación activa" (es el 409 `REASIGNACION_REQUIERE_CONFIRMACION` de G64-02).

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g62_v2.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G62-V2.html`
- Aserciones: 11 total, 2 fallidas (incluye el login)
- Nota: Discrepancia con la matriz (decisión 7): el backend responde 404 para sensor inexistente.
- Fallo: Sensor inexistente -> 422 (consolidado) — expected response to have status code 422 but got 404
- Fallo: Dispositivo inexistente -> 404 — expected response to have status code 404 but got 422
