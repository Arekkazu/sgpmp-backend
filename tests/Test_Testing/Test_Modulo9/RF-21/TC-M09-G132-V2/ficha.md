# TC-M09-G132-V2 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA parcial (7/7): DELETE 405 y baja lógica 200; dependencias no creadas

### G132-02 — Baja lógica vs. eliminación física (nuevo)
- **Tipo:** Integridad referencial · **Ejecutable:** Sí.
- **Pasos:** cuatro dispositivos, cada uno con **una sola** dependencia (telemetría, alerta, sensor asociado, historial de estado) → eliminación física 405 en cada caso. Baja lógica (`activo=false`) → 200.
- **Nota:** no hay endpoint de eliminación física verificado aún; comprobar antes de ejecutar.

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g132_v2.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G132-V2.html`
- Aserciones: 7 total, 0 fallidas (incluye el login)
