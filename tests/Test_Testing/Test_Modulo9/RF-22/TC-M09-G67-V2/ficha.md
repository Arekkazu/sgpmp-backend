# TC-M09-G67-V2 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** NO EJECUTADO — Requiere inyección de fallo en la auditoría de la reasignación. Esperado: sensor sigue en A y no existe asociación en B.

### G67-02 — Rollback de asociación y reasignación
- **Tipo:** Atomicidad · **Ejecutable:** Solo con inyección de fallo en auditoría. Esperado ante fallo: el sensor sigue en A; ninguna asociación SUPERADA; no existe asociación en B.
