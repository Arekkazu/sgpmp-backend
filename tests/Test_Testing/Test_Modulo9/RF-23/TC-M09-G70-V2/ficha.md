# TC-M09-G70-V2 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA (16/16)

### G70-02 — Validaciones y desenlaces
- **Tipo:** Validación · **Ejecutable:** Sí para 404, rango (400), intervalo vs frecuencia (400), 202 PENDIENTE; **504 NO_CONF** requiere broker sin ACK (DEV).
- **Bordes del rango:** MIN−1 / MIN / MAX / MAX+1 — tomar MIN y MAX del catálogo del tipo **antes** de ejecutar.
- **Intervalo vs frecuencia:** −1 / igual / +1 (aceptar igualdad).
- **Sin ACK:** medir 29 / 30 / 31 s.
- **Concurrencia:** 409 `CONFIG_PENDIENTE_EXISTENTE` verificado en TEST.

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g70_v2.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G70-V2.html`
- Aserciones: 16 total, 0 fallidas (incluye el login)
