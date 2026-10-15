# TC-M09-G58 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA (13/13)

### G58-02 — Restricción de rol
- **Tipo:** Seguridad (OWASP API5) · **Ejecutable:** Sí.
- **Pasos:** repetir alta SENSOR y CAMARA con Productor, Veterinario y Contador. Esperado 403 y sin persistencia.

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g58.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G58.html`
- Aserciones: 13 total, 0 fallidas (incluye el login)
