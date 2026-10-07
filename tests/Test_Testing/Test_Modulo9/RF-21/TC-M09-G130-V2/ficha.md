# TC-M09-G130-V2 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA (11/11): validación de atributos de visión ya activa

### G130-02 — Atributos de visión: rangos e ignorado silencioso (nuevo)
- **Tipo:** Valores límite · **Estado:** **Esperado en rojo** (CAMARA no implementado).
- **Casos:** ausencia de cada atributo en CAMARA → debería ser 400; `fps` 0 / 1 / 60 / 61; `area_cobertura_m2` −1 / 0 / 0.01; atributos de visión en SENSOR → debería ser 201 con atributos nulos.
- **Observado:** cualquier valor de `fps` y `resolucion` se acepta sin validar porque el DTO no los declara.

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g130_v2.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G130-V2.html`
- Aserciones: 11 total, 0 fallidas (incluye el login)
