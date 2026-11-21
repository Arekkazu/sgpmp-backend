# TC-M09-G128 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-09, reintento1):** BLOQUEADO, pendiente de decisión de alcance LoRaWAN (confirmado por código, 2/2).

### G128-02 — Ataques a LoRaWAN
- **Estado:** Pendiente de decisión de alcance. El chequeo estructural previo (sesión 2026-10-04/05, commit `cfa905d0`) se había perdido del árbol de trabajo con la reestructuración "-02"; se recuperó del historial de git y se actualizó.

## Reintento1 (2026-10-09)
- Script: `test_tc_m09_g128_sin_soporte_lorawan_reintento1.py` (pytest, inspección de código/DDL — sin red/BD)
- Reporte: `resultados/resultado_TC-M09-G128_reintento1.html`
- 2/2 passed: sigue sin existir ningún código/DDL con soporte LoRaWAN (barrido de `src/`, `alembic/`, `anotaciones/`); el contrato de configuración remota sigue sin `protocolo`.
