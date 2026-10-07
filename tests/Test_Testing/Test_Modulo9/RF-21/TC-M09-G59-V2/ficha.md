# TC-M09-G59-V2 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA (8/8)

### G59-02 — Conflicto de serial en sincronización offline
- **Tipo:** Integración (cliente) · **Ejecutable:** **Parcial.** La cola offline vive en el cliente y se prueba con Cypress en el frontend; aquí solo se verifica que el backend devuelva 409 `SERIAL_DUPLICADO` y no cree un segundo dispositivo. Ya cubierto por `TC-M09-G59` (reintento1, 12/12).

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g59_v2.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G59-V2.html`
- Aserciones: 8 total, 0 fallidas (incluye el login)
