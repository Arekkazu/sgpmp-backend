# TC-M09-G73-02 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** NO EJECUTADO (ver Resultados_M09_RF21-23_2026-10-06.md)

### G73-02 — Atomicidad ante fallo del historial
- **Tipo:** Atomicidad · **Ejecutable:** Solo con inyección de fallo y cliente MQTT para verificar que **no se publique**.
- **Esperado:** 500 con rollback y **ningún mensaje en el broker**.
