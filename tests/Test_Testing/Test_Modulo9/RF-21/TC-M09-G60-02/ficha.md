# TC-M09-G60-02 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** NO EJECUTADO — Requiere inyección de fallo en la auditoría (no disponible en caja negra en TEST). Verificar rollback en BD.

### G60-02 — Rollback por fallo de auditoría
- **Tipo:** Atomicidad · **Ejecutable:** Solo con inyección de fallo en auditoría (no disponible en TEST desde caja negra). Verificar en BD que SENSOR y CAMARA hacen rollback completo.
