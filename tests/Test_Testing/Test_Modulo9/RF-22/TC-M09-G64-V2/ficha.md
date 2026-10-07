# TC-M09-G64-V2 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA parcial (7/7): 409 y reasignación con confirmar; cascada pendiente de activos

### G64-02 — Reasignación y cascada RF-49
- **Tipo:** Funcional/Integración · **Ejecutable:** Sí, con datos de prueba (sensor con activos AMBIENTAL, POBLACIONAL y DIRECTA).
- **Escenarios (7):** 409 `REASIGNACION_REQUIERE_CONFIRMACION` al reasignar sin `confirmar`; reenvío con `confirmar=true` cierra la anterior y crea la nueva; AMBIENTAL y POBLACIONAL → SUPERADA; **DIRECTA permanece ACTIVA**; sin recreación automática en destino; auditoría por cada marca.
- **Variantes de área destino:** 0, 1 y varios activos biológicos.
- **Separar en grupo propio** los escenarios 3–7 si se prefiere granularidad.

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g64_v2.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G64-V2.html`
- Aserciones: 7 total, 0 fallidas (incluye el login)
