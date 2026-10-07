# TC-M09-G133-02 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** FALLA contra matriz (6/8): dispositivo inexistente devuelve 422 SENSOR_DISPOSITIVO_INVALIDO

### G133-02 — Precedencia del orden de validación (nuevo)
- **Estado:** Ejecutable para el orden declarado (dispositivo → sensor → área → área activa → asociación previa → duplicado).
- **Abierto:** dónde entra la validación de `punto_instalacion` (decisión 6).

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g133_02.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G133-02.html`
- Aserciones: 8 total, 2 fallidas (incluye el login)
- Nota: El backend valida primero la pareja sensor-dispositivo: un dispositivo inexistente produce 422 en vez de 404 (orden de la matriz: dispositivo → sensor → área).
- Fallo: Dispositivo y area inexistentes con sensor valido -> 404 DISPOSITIVO_NO_ENCONTRADO — expected response to have status code 404 but got 422
- Fallo: Dispositivo y area inexistentes con sensor valido -> 404 DISPOSITIVO_NO_ENCONTRADO — expected 'SENSOR_DISPOSITIVO_INVALIDO' to deeply equal 'DISPOSITIVO_NO_ENCONTRADO'
