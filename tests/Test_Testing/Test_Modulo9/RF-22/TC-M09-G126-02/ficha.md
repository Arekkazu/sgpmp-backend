# TC-M09-G126-02 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA parcial (7/7): sin token, rol, forzado de estado; IDOR pendiente de 2a finca

### G126-02 — Ataques al control de acceso por objeto
- **Tipo:** Seguridad (OWASP API1/API3) · **Ejecutable:** Sí.
- **Escenarios:** IDOR con `area_id` de otra finca; `sensor_id` de otra finca (422 sin revelar nombres ajenos); mass assignment; consulta ajena por URL; **forzado del estado de cascada vía payload** (el más valioso).
- **Dependencia:** la respuesta de sensor ajeno (404 vs 403) depende de la decisión 1 (§9).

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g126_02.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G126-02.html`
- Aserciones: 7 total, 0 fallidas (incluye el login)
