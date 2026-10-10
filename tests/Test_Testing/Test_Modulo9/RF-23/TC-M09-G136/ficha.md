# TC-M09-G136 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-09, reintento1):** BLOQUEADO (confirmado por código, 2/2) — sigue sin existir `fps` en el contrato de escritura.

### G136-02 — Parámetros por categoría / fps (nuevo)
- **Estado: BLOQUEADO.** `ConfigurarRemotamenteDTO` solo tiene `frecuencia_captura`/`intervalo_transmision`; no tiene `fps`. RF-23 v1.1 no define qué código devuelve enviar `frecuencia_captura` a una CAMARA (§8.2). Bloqueo heredado de G134-02. Nota: el `fps` que sí existe en `GET /dispositivos-iot/{id}` (TC-M09-G57) es de solo lectura (siempre `null`), un contrato distinto del de escritura que este TC necesita.

## Reintento1 (2026-10-09)
- Script: `test_tc_m09_g136_sin_fps_reintento1.py` (pytest, inspección de código — sin red/BD)
- Reporte: `resultados/resultado_TC-M09-G136_reintento1.html`
- 2/2 passed.
