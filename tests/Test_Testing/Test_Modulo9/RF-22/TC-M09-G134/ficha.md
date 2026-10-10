# TC-M09-G134 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-09, reintento1):** BLOQUEADO (confirmado por código, 2/2) — sigue sin existir un campo de cámara.

### G134-02 — Asociación cámara→área (nuevo)
- **Estado: BLOQUEADO.** RF-22 v1.2 no tiene campo para identificar una cámara (`AsociarSensorAreaDTO` solo acepta `id_dispositivo_iot`, `id_infraestructura`, `punto_instalacion`, `confirmar`). Se desbloquea cuando RF-22 publique el campo y los códigos de flujo alterno.

## Reintento1 (2026-10-09)
- Script: `test_tc_m09_g134_sin_campo_camara_reintento1.py` (pytest, inspección de código — sin red/BD)
- Reporte: `resultados/resultado_TC-M09-G134_reintento1.html`
- 2/2 passed (confirman la ausencia del campo/categoría de cámara).

---
