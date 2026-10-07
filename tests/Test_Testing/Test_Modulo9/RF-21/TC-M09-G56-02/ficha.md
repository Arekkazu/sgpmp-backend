# TC-M09-G56-02 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA parcial: 409, 400, 400, 422

### G56-02 — Validación de datos base
- **Tipo:** Validación · **Ejecutable:** Sí.
- **Casos:**
  - `serial` 49 / 50 / 51 caracteres: 201 / 201 / **400**. Verificado: 51 → 400.
  - `descripcion` 99 / 100 / 101: pendiente de ejecutar.
  - `id_tipo_dispositivo=9999` → **422**. Verificado.
  - Área inexistente o inactiva → 422 (pendiente).
  - Serial duplicado → 409 (pendiente).
- **Hueco a probar:** serial de 50 caracteres con caracteres multibyte (el tipo es `varchar(50)`; comprobar que no se trunque en BD).
