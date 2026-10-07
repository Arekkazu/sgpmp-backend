# TC-M09-G132-02 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** NO EJECUTADO (ver Resultados_M09_RF21-23_2026-10-06.md)

### G132-02 — Baja lógica vs. eliminación física (nuevo)
- **Tipo:** Integridad referencial · **Ejecutable:** Sí.
- **Pasos:** cuatro dispositivos, cada uno con **una sola** dependencia (telemetría, alerta, sensor asociado, historial de estado) → eliminación física 405 en cada caso. Baja lógica (`activo=false`) → 200.
- **Nota:** no hay endpoint de eliminación física verificado aún; comprobar antes de ejecutar.
