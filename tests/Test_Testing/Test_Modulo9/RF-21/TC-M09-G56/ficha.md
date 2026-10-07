# TC-M09-G56 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** FALLA contra matriz (12/13): área inexistente 404 vs 422

### G56-02 — Validación de datos base
- **Tipo:** Validación · **Ejecutable:** Sí.
- **Casos:**
  - `serial` 49 / 50 / 51 caracteres: 201 / 201 / **400**. Verificado: 51 → 400.
  - `descripcion` 99 / 100 / 101: pendiente de ejecutar.
  - `id_tipo_dispositivo=9999` → **422**. Verificado.
  - Área inexistente o inactiva → 422 (pendiente).
  - Serial duplicado → 409 (pendiente).
- **Hueco a probar:** serial de 50 caracteres con caracteres multibyte (el tipo es `varchar(50)`; comprobar que no se trunque en BD).

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g56.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G56.html`
- Aserciones: 13 total, 1 fallidas (incluye el login)
- Fallo: Area inexistente -> 422 (matriz) — expected response to have status code 422 but got 404
