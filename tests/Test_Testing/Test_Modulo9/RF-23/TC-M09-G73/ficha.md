# TC-M09-G73 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** NO EJECUTADO — Requiere inyección de fallo en el historial y un cliente MQTT para confirmar que no se publica ningún mensaje.

### G73-02 — Atomicidad ante fallo del historial
- **Tipo:** Atomicidad · **Ejecutable:** Solo con inyección de fallo y cliente MQTT para verificar que **no se publique**.
- **Esperado:** 500 con rollback y **ningún mensaje en el broker**.
