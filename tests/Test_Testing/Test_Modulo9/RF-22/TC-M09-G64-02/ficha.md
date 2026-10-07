# TC-M09-G64-02 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** NO EJECUTADO (ver Resultados_M09_RF21-23_2026-10-06.md)

### G64-02 — Reasignación y cascada RF-49
- **Tipo:** Funcional/Integración · **Ejecutable:** Sí, con datos de prueba (sensor con activos AMBIENTAL, POBLACIONAL y DIRECTA).
- **Escenarios (7):** 409 `REASIGNACION_REQUIERE_CONFIRMACION` al reasignar sin `confirmar`; reenvío con `confirmar=true` cierra la anterior y crea la nueva; AMBIENTAL y POBLACIONAL → SUPERADA; **DIRECTA permanece ACTIVA**; sin recreación automática en destino; auditoría por cada marca.
- **Variantes de área destino:** 0, 1 y varios activos biológicos.
- **Separar en grupo propio** los escenarios 3–7 si se prefiere granularidad.
