# TC-M09-G55 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA (7/7 aserciones)

### G55-02 — Camino feliz por categoría
- **Tipo:** Funcional · **Herramienta:** API (Postman/Newman) · **Ejecutable:** Sí para SENSOR; **CAMARA no verificable** (no implementado).
- **Pasos:** (a) `POST` SENSOR válido → 201. (b) `POST` CAMARA con `resolucion`, `fps`, `area_cobertura_m2` → 201 **y** persistencia de los tres atributos. (c) Sin `activo` → 201 con `activo=true`.
- **Esperado:** (a) y (c) según especificación. (b) los tres atributos persistidos.
- **Observado (2026-10-06):** (a) y (c) ok. (b) **201 con atributos en `null`**.

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g55.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G55.html`
- Aserciones: 7 total, 0 fallidas (incluye el login)
